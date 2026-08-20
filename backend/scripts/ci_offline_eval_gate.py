"""CI offline eval gate (no LLM, no live API).

Runs lightweight checks for eval dimensions scaffolded in eval/runners/.
Exit 0 when all configured thresholds pass.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _threshold(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


def _check_generation() -> tuple[bool, str, float | None]:
    from eval.runners.generation_eval import run_eval

    report = run_eval(live=False, limit=0)
    ready = bool(report["dataset_validation"]["valid"])
    total = report["dataset_validation"]["total"]
    min_prompts = int(os.environ.get("GENERATION_DATASET_MIN", "50"))
    ok = ready and total >= min_prompts
    return ok, f"dataset_ready={ready} total={total}", None


def _check_code_quality() -> tuple[bool, str, float | None]:
    from eval.runners.code_quality_eval import run_eval

    report = run_eval()
    rate = float(report["summary"]["structure_detection_accuracy"])
    min_rate = _threshold("CODE_QUALITY_STRUCTURE_MIN", 0.90)
    ok = rate >= min_rate
    return ok, f"structure_detection_accuracy={rate:.1%}", rate


def _check_reliability() -> tuple[bool, str, float | None]:
    from eval.runners.reliability_eval import run_eval

    report = run_eval()
    rate = float(report["summary"]["unit_pass_rate"])
    min_rate = _threshold("RELIABILITY_UNIT_PASS_MIN", 0.90)
    ok = rate >= min_rate
    return ok, f"unit_pass_rate={rate:.1%}", rate


def _check_preference() -> tuple[bool, str, float | None]:
    from eval.runners.preference_eval import run_eval

    report = run_eval()
    rate = float(report["summary"]["cross_session_injection_rate"])
    min_rate = _threshold("PREFERENCE_INJECTION_MIN", 1.0)
    ok = rate >= min_rate
    return ok, f"cross_session_injection_rate={rate:.1%}", rate


def _check_performance() -> tuple[bool, str, float | None]:
    from eval.runners.performance_eval import run_eval

    report = run_eval()
    p95 = float(report["summary"]["guard_p95_ms"])
    max_p95 = _threshold("PERFORMANCE_GUARD_P95_MAX_MS", 50.0)
    ok = p95 <= max_p95
    return ok, f"guard_p95_ms={p95:.3f}", p95


def run() -> int:
    checks: list[tuple[str, Callable[[], tuple[bool, str, float | None]]]] = [
        ("generation", _check_generation),
        ("code_quality", _check_code_quality),
        ("reliability", _check_reliability),
        ("preference", _check_preference),
        ("performance", _check_performance),
    ]

    results: list[tuple[str, bool, str]] = []
    for name, fn in checks:
        ok, detail, _ = fn()
        results.append((name, ok, detail))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    ts = datetime.now(UTC).isoformat()
    out_dir = REPO_ROOT / "tmp"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "ci_offline_eval_report.md"

    lines = [
        "# CI Offline Eval Gate",
        "",
        f"- Timestamp (UTC): {ts}",
        "",
        "| Dimension | Status | Detail |",
        "|---|---|---|",
    ]
    for name, ok, detail in results:
        lines.append(f"| {name} | {'✅' if ok else '❌'} | {detail} |")

    all_ok = all(ok for _, ok, _ in results)
    lines += [
        "",
        f"**Overall**: {'PASS' if all_ok else 'FAIL'}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(md_path)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(run())
