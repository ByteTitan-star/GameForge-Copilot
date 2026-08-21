"""Dimension 4: Performance benchmark.

Issue: #117

- Offline: guard quick_filter latency
- Derived: e2e + per-phase from generation_eval JSON
- Optional: concurrency bench (EVAL_PERF_CONCURRENCY_BENCH=1)
- Sandbox: app.sandbox.benchmark.run_benchmark
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "backend"))

from eval.runners._common import (
    DOCS_EVALS_DIR,
    base_report_meta,
    load_dataset,
    percentile,
    report_header,
    setup_backend_path,
    write_json_report,
    write_markdown,
)

setup_backend_path()
from app.core.config import settings  # noqa: E402
from app.forge.guard import quick_filter  # noqa: E402

settings.audit_quick_filter = True
settings.audit_lexicon_enabled = True


def latency_degradation_pct(*, p95_n1: float, p95_n3: float) -> float:
    if p95_n1 <= 0:
        return 0.0
    return round((p95_n3 - p95_n1) / p95_n1 * 100.0, 4)


def throughput_per_hour(*, successes: int, wall_clock_s: float) -> float:
    if wall_clock_s <= 0:
        return 0.0
    return round(successes / wall_clock_s * 3600.0, 4)


def summarize_phase_latencies(per_run: list[dict[str, Any]]) -> dict[str, Any]:
    walls = [float(r["wall_clock_s"]) for r in per_run if r.get("wall_clock_s") is not None]
    plan: list[float] = []
    code: list[float] = []
    for row in per_run:
        for phase in row.get("phases") or []:
            name = str(phase.get("name") or "").lower()
            try:
                dur = float(phase.get("duration_s"))
            except (TypeError, ValueError):
                continue
            if name in {"plan", "planning"}:
                plan.append(dur)
            elif name in {"code", "code_gen", "generate", "repair"}:
                code.append(dur)
    walls_s = sorted(walls)
    plan_s = sorted(plan)
    code_s = sorted(code)
    return {
        "runs": len(per_run),
        "e2e_p50_s": percentile(walls_s, 0.50) if walls_s else None,
        "e2e_p95_s": percentile(walls_s, 0.95) if walls_s else None,
        "plan_latency_p50_s": percentile(plan_s, 0.50) if plan_s else None,
        "code_gen_latency_p50_s": percentile(code_s, 0.50) if code_s else None,
    }


def _guard_latencies(texts: list[str]) -> list[float]:
    latencies: list[float] = []
    for text in texts:
        t0 = time.perf_counter()
        quick_filter(text, force=True)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def _load_latest_generation() -> tuple[dict[str, Any] | None, str | None]:
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    candidates = sorted(reports_dir.glob("*_generation_eval.json"), reverse=True)
    for candidate in candidates:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        if data.get("per_run"):
            return data, candidate.name
    return None, None


def _run_sandbox_benchmark() -> dict[str, Any] | None:
    try:
        from app.sandbox.benchmark import run_benchmark
    except Exception as exc:  # noqa: BLE001
        return {"error": f"import_failed:{type(exc).__name__}"}
    try:
        return asyncio.run(run_benchmark(rounds=5))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"benchmark_failed:{type(exc).__name__}:{exc}"}


def _concurrency_bench_note() -> dict[str, Any]:
    """Document how to run concurrency bench; live runs are opt-in."""
    return {
        "enabled": False,
        "instructions": (
            "Set EVAL_PERF_CONCURRENCY_BENCH=1 with EVAL_LIVE credentials to measure "
            "N=1,2,3 throughput via generation_eval (subset from performance_subset.json)."
        ),
    }


def run_eval(*, concurrency_bench: bool = False) -> dict[str, Any]:
    adversarial = load_dataset("adversarial.json")
    generation = load_dataset("generation.json")
    texts = [c["prompt"] for c in adversarial] + [c["prompt"] for c in generation]

    latencies = _guard_latencies(texts)
    sorted_lat = sorted(latencies)
    guard_stats = {
        "samples": len(latencies),
        "guard_p50_ms": round(percentile(sorted_lat, 0.50), 3),
        "guard_p95_ms": round(percentile(sorted_lat, 0.95), 3),
        "guard_p99_ms": round(percentile(sorted_lat, 0.99), 3),
    }

    gen_data, source_name = _load_latest_generation()
    phase_stats = None
    if gen_data is not None:
        phase_stats = summarize_phase_latencies(list(gen_data.get("per_run") or []))
        phase_stats["source_report"] = source_name

    sandbox = _run_sandbox_benchmark()
    sandbox_p95 = None
    if isinstance(sandbox, dict):
        local = sandbox.get("local_dry_run") or {}
        if local.get("exec_ms_p95") is not None:
            sandbox_p95 = float(local["exec_ms_p95"])

    concurrency = _concurrency_bench_note()
    if concurrency_bench:
        concurrency = {
            "enabled": True,
            "note": (
                "Live concurrency harness not auto-executed in this runner revision; "
                "use EVAL_CONCURRENCY with generation_eval --live --limit 10 for N=1,2,3 "
                "and compute latency_degradation_pct / throughput_per_hour offline."
            ),
            "helpers": {
                "latency_degradation_pct": latency_degradation_pct(
                    p95_n1=100.0, p95_n3=150.0
                ),
                "example_throughput_per_hour": throughput_per_hour(
                    successes=10, wall_clock_s=1800.0
                ),
            },
        }

    summary = {
        "mode": "offline_guard_baseline",
        **guard_stats,
        "sandbox_exec_p95_ms": sandbox_p95,
        "e2e_p50_s": phase_stats.get("e2e_p50_s") if phase_stats else None,
        "e2e_p95_s": phase_stats.get("e2e_p95_s") if phase_stats else None,
        "plan_latency_p50_s": phase_stats.get("plan_latency_p50_s") if phase_stats else None,
        "code_gen_latency_p50_s": (
            phase_stats.get("code_gen_latency_p50_s") if phase_stats else None
        ),
    }

    report = base_report_meta(
        dimension="performance",
        runner="eval/runners/performance_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["generation_stats"] = phase_stats
    report["sandbox_benchmark"] = sandbox
    report["concurrency"] = concurrency
    report["note"] = (
        "Guard latency always measured. Phase/e2e stats require enriched generation_eval "
        "JSON. Sandbox p95 from local dry-run benchmark. Concurrency N=1,2,3 is opt-in."
    )
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="Performance Benchmark Report",
        summary=(
            f"Guard quick_filter latency over **{s['samples']}** prompts: "
            f"p50={s['guard_p50_ms']:.3f}ms, p95={s['guard_p95_ms']:.3f}ms."
        ),
        runner="eval/runners/performance_eval.py",
        dataset="adversarial.json + generation.json",
        dataset_count=s["samples"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    lines += [
        f"| guard_p50_ms | {s['guard_p50_ms']:.3f}ms | documented | - |",
        f"| guard_p95_ms | {s['guard_p95_ms']:.3f}ms | documented | - |",
        f"| guard_p99_ms | {s['guard_p99_ms']:.3f}ms | documented | - |",
        f"| e2e_p50_s | {s['e2e_p50_s'] or 'n/a'} | tracked | - |",
        f"| e2e_p95_s | {s['e2e_p95_s'] or 'n/a'} | tracked | - |",
        f"| plan_latency_p50_s | {s.get('plan_latency_p50_s') or 'n/a'} | tracked | - |",
        f"| code_gen_latency_p50_s | {s.get('code_gen_latency_p50_s') or 'n/a'} | tracked | - |",
        f"| sandbox_exec_p95_ms | {s.get('sandbox_exec_p95_ms') or 'n/a'} | <= 30000 | - |",
        "",
        "## 7. Conclusion",
        "",
        report["note"],
        "",
    ]
    return write_markdown(DOCS_EVALS_DIR / "performance-eval-report.md", lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Performance benchmark eval")
    parser.add_argument(
        "--concurrency-bench",
        action="store_true",
        help="Document/enable concurrency bench helpers",
    )
    args = parser.parse_args()
    concurrency = args.concurrency_bench or os.environ.get(
        "EVAL_PERF_CONCURRENCY_BENCH", ""
    ).lower() in {"1", "true", "yes"}
    report = run_eval(concurrency_bench=concurrency)
    json_path = write_json_report("performance_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"guard_p95_ms={s['guard_p95_ms']}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
