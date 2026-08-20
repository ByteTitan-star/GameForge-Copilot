"""Dimension 4: Performance benchmark (guard latency baseline + report aggregation).

Issue: #117

Offline mode measures quick_filter latency distribution across adversarial +
generation prompts. Live e2e phase timings require generation_eval JSON.
"""

from __future__ import annotations

import json
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


def _guard_latencies(texts: list[str]) -> list[float]:
    latencies: list[float] = []
    for text in texts:
        t0 = time.perf_counter()
        quick_filter(text, force=True)
        latencies.append((time.perf_counter() - t0) * 1000)
    return latencies


def _load_generation_phase_stats() -> dict[str, Any] | None:
    reports_dir = Path(__file__).resolve().parent.parent / "reports"
    candidates = sorted(reports_dir.glob("*_generation_eval.json"), reverse=True)
    if not candidates:
        return None
    data = json.loads(candidates[0].read_text(encoding="utf-8"))
    per_run = data.get("per_run") or []
    if not per_run:
        return None
    wall = [r.get("wall_clock_s", 0) for r in per_run if r.get("wall_clock_s")]
    if not wall:
        return None
    wall_sorted = sorted(wall)
    return {
        "source_report": str(candidates[0].name),
        "runs": len(wall),
        "e2e_p50_s": percentile(wall_sorted, 0.50),
        "e2e_p95_s": percentile(wall_sorted, 0.95),
    }


def run_eval() -> dict[str, Any]:
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

    gen_stats = _load_generation_phase_stats()
    summary = {
        "mode": "offline_guard_baseline",
        **guard_stats,
        "sandbox_exec_p95_ms": None,
        "e2e_p50_s": gen_stats["e2e_p50_s"] if gen_stats else None,
        "e2e_p95_s": gen_stats["e2e_p95_s"] if gen_stats else None,
    }

    report = base_report_meta(
        dimension="performance",
        runner="eval/runners/performance_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["generation_stats"] = gen_stats
    report["note"] = (
        "Full performance benchmark (sandbox p95, concurrent throughput) requires "
        "generation_eval --live and sandbox benchmark integration."
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
        "",
        "## 7. Conclusion",
        "",
        report["note"],
        "",
    ]
    return write_markdown(DOCS_EVALS_DIR / "performance-eval-report.md", lines)


def main() -> None:
    report = run_eval()
    json_path = write_json_report("performance_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"guard_p95_ms={s['guard_p95_ms']}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
