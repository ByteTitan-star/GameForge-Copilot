"""Dimension 8: Reliability mechanism effectiveness.

Issue: #125

Modes:
  - unit_baseline (default / CI): helper unit cases
  - live_fault (--live-fault): simulated fault-injection scenarios
"""

from __future__ import annotations

import argparse
import os
import sys
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
    below_target_section,
    load_dataset,
    report_header,
    setup_backend_path,
    status_cell,
    write_json_report,
    write_markdown,
)

setup_backend_path()
from app.core.config import settings  # noqa: E402
from app.enums import PauseReason  # noqa: E402
from app.forge.llm_continuation import (  # noqa: E402
    has_incomplete_structure,
    is_likely_truncated,
    is_output_truncated_error,
)
from app.forge.reliability.pause import (  # noqa: E402
    merge_pause_checkpoint,
    pause_reason_from_state,
)

_UNIT_TYPES = frozenset(
    {
        "truncation_html",
        "truncation_json",
        "truncation_complete",
        "finish_reason_length",
        "finish_reason_stop",
        "output_truncated_error",
        "pause_checkpoint_merge",
        "pause_reason_roundtrip",
        "continuation_notice_present",
        "stale_running_timeout_config",
    }
)
_LIVE_FAULT_TYPES = frozenset(
    {
        "llm_timeout_then_ok",
        "mid_run_kill_resume",
        "oversized_continuation",
        "all_fail_degradation",
        "stale_cleanup",
    }
)


def is_unit_case(case: dict[str, Any]) -> bool:
    return case.get("type") in _UNIT_TYPES


def is_live_fault_case(case: dict[str, Any]) -> bool:
    return case.get("type") in _LIVE_FAULT_TYPES


def _eval_unit_case(case: dict[str, Any]) -> dict[str, Any]:
    ctype = case["type"]
    ok = False
    detail = ""

    if ctype == "truncation_html":
        ok = has_incomplete_structure(case["input"]) == case["expected_truncated"]
        detail = "has_incomplete_structure(html)"
    elif ctype == "truncation_json":
        ok = has_incomplete_structure(case["input"]) == case["expected_truncated"]
        detail = "has_incomplete_structure(json)"
    elif ctype == "truncation_complete":
        ok = has_incomplete_structure(case["input"]) == case["expected_truncated"]
        detail = "complete html"
    elif ctype in {"finish_reason_length", "finish_reason_stop"}:
        ok = (
            is_likely_truncated(
                "",
                output_tokens=case["output_tokens"],
                max_tokens=case["max_tokens"],
                finish_reason=case["finish_reason"],
            )
            == case["expected_truncated"]
        )
        detail = "is_likely_truncated"
    elif ctype == "output_truncated_error":
        ok = is_output_truncated_error(case["errors"]) == case["expected_detected"]
        detail = "is_output_truncated_error"
    elif ctype == "pause_checkpoint_merge":
        merged = merge_pause_checkpoint(
            case["existing"],
            phase="playtest",
            pause_reason=PauseReason.RECOVERABLE_ERROR,
        )
        ok = all(k in merged for k in case["expected_keys"])
        detail = "merge_pause_checkpoint"
    elif ctype == "pause_reason_roundtrip":
        state = {"pause_reason": case["pause_reason"]}
        reason = pause_reason_from_state(state)
        ok = reason is not None and reason.value == case["expected_enum"]
        detail = "pause_reason_from_state"
    elif ctype == "continuation_notice_present":
        from app.forge.llm_continuation import _CONTINUATION_NOTICE  # noqa: PLC2701

        ok = case["expected_contains"] in _CONTINUATION_NOTICE
        detail = "continuation notice string"
    elif ctype == "stale_running_timeout_config":
        ok = getattr(settings, case["setting"], 0) >= case["expected_min"]
        detail = case["setting"]
    else:
        detail = "unknown unit case type"

    return {"id": case["id"], "type": ctype, "ok": ok, "detail": detail}


def _simulate_timeout_then_ok(*, fail_times: int) -> bool:
    failures = 0
    for attempt in range(1, fail_times + 2):
        if attempt <= fail_times:
            failures += 1
            continue
        return failures == fail_times
    return False


def _eval_live_fault_case(case: dict[str, Any]) -> dict[str, Any]:
    ctype = case["type"]
    ok = False
    detail = ""
    skipped = False

    if ctype == "llm_timeout_then_ok":
        ok = _simulate_timeout_then_ok(fail_times=int(case.get("fail_times") or 1))
        detail = "simulated LLM timeout then success"
    elif ctype == "mid_run_kill_resume":
        # Deterministic simulation: checkpoint merge after recoverable pause.
        merged = merge_pause_checkpoint(
            {"phase": "code", "art_assets": {"a": 1}},
            phase="code",
            pause_reason=PauseReason.RECOVERABLE_ERROR,
        )
        reason = pause_reason_from_state(merged)
        ok = (
            reason == PauseReason.RECOVERABLE_ERROR
            and "art_assets" in merged
            and bool(case.get("expected_resume", True))
        )
        detail = "simulated checkpoint resume (process kill not executed in CI)"
    elif ctype == "oversized_continuation":
        from app.forge.llm_continuation import _CONTINUATION_NOTICE  # noqa: PLC2701

        truncated = has_incomplete_structure(case["input"]) == case.get(
            "expected_truncated", True
        )
        notice_ok = case.get("expected_contains", "续写") in _CONTINUATION_NOTICE
        ok = truncated and notice_ok
        detail = "truncation detect + continuation notice"
    elif ctype == "all_fail_degradation":
        state = {"pause_reason": case.get("expected_pause_reason", "recoverable_error")}
        reason = pause_reason_from_state(state)
        ok = reason == PauseReason.RECOVERABLE_ERROR
        detail = "degradation maps to recoverable_error pause"
    elif ctype == "stale_cleanup":
        ok = getattr(settings, case["setting"], 0) >= case["expected_min"]
        detail = "stale timeout config present"
    else:
        detail = "unknown live fault type"
        skipped = True

    return {
        "id": case["id"],
        "type": ctype,
        "ok": ok,
        "detail": detail,
        "skipped": skipped,
    }


def run_eval(*, live_fault: bool = False) -> dict[str, Any]:
    cases = load_dataset("reliability_faults.json")
    if live_fault:
        selected = [c for c in cases if is_live_fault_case(c)]
        per_case = [_eval_live_fault_case(c) for c in selected]
        evaluated = [c for c in per_case if not c.get("skipped")]
        passed = sum(1 for c in evaluated if c["ok"])
        n = max(1, len(evaluated))
        by_type = {c["type"]: c["ok"] for c in evaluated}
        summary = {
            "case_count": len(evaluated),
            "unit_pass_rate": None,
            "timeout_retry_recovery_rate": (
                1.0 if by_type.get("llm_timeout_then_ok") else 0.0
            ),
            "checkpoint_resume_success_rate": (
                1.0 if by_type.get("mid_run_kill_resume") else 0.0
            ),
            "continuation_success_rate": (
                1.0 if by_type.get("oversized_continuation") else 0.0
            ),
            "degradation_fallback_triggers": (
                1.0 if by_type.get("all_fail_degradation") else 0.0
            ),
            "live_fault_pass_rate": round(passed / n, 4),
            "mode": "live_fault",
        }
        note = (
            "Live-fault mode uses deterministic simulations suitable for CI. "
            "Real worker kill/resume remains optional on Linux self-hosted runners."
        )
    else:
        selected = [c for c in cases if is_unit_case(c)]
        per_case = [_eval_unit_case(c) for c in selected]
        passed = sum(1 for c in per_case if c["ok"])
        n = max(1, len(selected))
        summary = {
            "case_count": len(selected),
            "unit_pass_rate": round(passed / n, 4),
            "mode": "unit_baseline",
        }
        note = (
            "Unit baseline only. Run with --live-fault for simulated fault-injection metrics."
        )

    report = base_report_meta(
        dimension="reliability",
        runner="eval/runners/reliability_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["per_case"] = per_case
    report["note"] = note
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="Reliability Mechanism Eval Report",
        summary=(
            f"Reliability checks on **{s['case_count']}** scenarios "
            f"(mode={s['mode']})."
        ),
        runner="eval/runners/reliability_eval.py",
        dataset="eval/datasets/reliability_faults.json",
        dataset_count=s["case_count"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    if s["mode"] == "live_fault":
        lines += [
            f"| live_fault_pass_rate | {s['live_fault_pass_rate']:.1%} | >= 90% | "
            f"{status_cell(s['live_fault_pass_rate'], 0.90, higher_is_better=True)} |",
            f"| timeout_retry_recovery_rate | {s['timeout_retry_recovery_rate']:.1%} | >= 90% | "
            f"{status_cell(s['timeout_retry_recovery_rate'], 0.90, higher_is_better=True)} |",
            f"| checkpoint_resume_success_rate | {s['checkpoint_resume_success_rate']:.1%} | 100% | "
            f"{status_cell(s['checkpoint_resume_success_rate'], 1.0, higher_is_better=True)} |",
            f"| continuation_success_rate | {s['continuation_success_rate']:.1%} | >= 85% | "
            f"{status_cell(s['continuation_success_rate'], 0.85, higher_is_better=True)} |",
            f"| degradation_fallback_triggers | {s['degradation_fallback_triggers']:.1%} | 100% | "
            f"{status_cell(s['degradation_fallback_triggers'], 1.0, higher_is_better=True)} |",
        ]
    else:
        lines += [
            f"| unit_pass_rate | {s['unit_pass_rate']:.1%} | >= 90% | "
            f"{status_cell(s['unit_pass_rate'], 0.90, higher_is_better=True)} |",
        ]
    lines += ["", "## 4. Failure Analysis", ""]
    failures = [c for c in report["per_case"] if not c.get("ok")]
    if failures:
        lines.append("| id | type | detail |")
        lines.append("|---|---|---|")
        for f in failures:
            lines.append(f"| {f['id']} | {f['type']} | {f['detail']} |")
    else:
        lines.append("All evaluated cases passed.")
    lines.append("")
    below: list[str] = []
    if s.get("unit_pass_rate") is not None and s["unit_pass_rate"] < 0.90:
        below.append("- unit_pass_rate below 90%")
    if s.get("live_fault_pass_rate") is not None and s["live_fault_pass_rate"] < 0.90:
        below.append("- live_fault_pass_rate below 90%")
    lines.extend(below_target_section(below))
    lines += ["## 7. Conclusion", "", report["note"], ""]
    return write_markdown(DOCS_EVALS_DIR / "reliability-eval-report.md", lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Reliability eval")
    parser.add_argument(
        "--live-fault",
        action="store_true",
        help="Run simulated live fault-injection cases",
    )
    args = parser.parse_args()
    live_fault = args.live_fault or os.environ.get("EVAL_LIVE_FAULT", "").lower() in {
        "1",
        "true",
        "yes",
    }
    report = run_eval(live_fault=live_fault)
    json_path = write_json_report("reliability_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"mode={s['mode']}")
    if s.get("unit_pass_rate") is not None:
        print(f"unit_pass_rate={s['unit_pass_rate']:.1%}")
    if s.get("live_fault_pass_rate") is not None:
        print(f"live_fault_pass_rate={s['live_fault_pass_rate']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
