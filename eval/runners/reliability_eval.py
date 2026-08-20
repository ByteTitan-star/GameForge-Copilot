"""Dimension 8: Reliability mechanism effectiveness (unit-style baseline).

Issue: #125

Tests continuation detection, pause checkpoint merge, and error classification
without live fault injection or LLM calls.
"""

from __future__ import annotations

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
    OUTPUT_TRUNCATED_ERROR,
    has_incomplete_structure,
    is_likely_truncated,
    is_output_truncated_error,
)
from app.forge.reliability.pause import (  # noqa: E402
    merge_pause_checkpoint,
    pause_reason_from_state,
)


def _eval_case(case: dict[str, Any]) -> dict[str, Any]:
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
        detail = "unknown case type"

    return {"id": case["id"], "type": ctype, "ok": ok, "detail": detail}


def run_eval() -> dict[str, Any]:
    cases = load_dataset("reliability_faults.json")
    per_case = [_eval_case(c) for c in cases]
    passed = sum(1 for c in per_case if c["ok"])
    n = max(1, len(cases))
    summary = {
        "case_count": len(cases),
        "unit_pass_rate": round(passed / n, 4),
        "mode": "unit_baseline",
    }

    report = base_report_meta(
        dimension="reliability",
        runner="eval/runners/reliability_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["per_case"] = per_case
    report["note"] = (
        "Live fault injection (timeout retry, checkpoint resume under kill) "
        "requires integration tests with worker + PostgreSQL."
    )
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    from pathlib import Path

    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="Reliability Mechanism Eval Report",
        summary=(
            f"Unit-style reliability checks on **{s['case_count']}** scenarios. "
            f"Pass rate: **{s['unit_pass_rate']:.1%}**."
        ),
        runner="eval/runners/reliability_eval.py",
        dataset="eval/datasets/reliability_faults.json",
        dataset_count=s["case_count"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    lines += [
        f"| unit_pass_rate | {s['unit_pass_rate']:.1%} | >= 90% | "
        f"{status_cell(s['unit_pass_rate'], 0.90, higher_is_better=True)} |",
        "",
        "## 4. Failure Analysis",
        "",
    ]
    failures = [c for c in report["per_case"] if not c["ok"]]
    if failures:
        lines.append("| id | type | detail |")
        lines.append("|---|---|---|")
        for f in failures:
            lines.append(f"| {f['id']} | {f['type']} | {f['detail']} |")
    else:
        lines.append("All unit baseline cases passed.")
    lines.append("")
    lines.extend(
        below_target_section(
            [
                "- unit_pass_rate below 90%"
                if s["unit_pass_rate"] < 0.90
                else ""
            ]
        )
    )
    lines += ["## 7. Conclusion", "", report["note"], ""]
    return write_markdown(DOCS_EVALS_DIR / "reliability-eval-report.md", lines)


def main() -> None:
    report = run_eval()
    json_path = write_json_report("reliability_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"unit_pass_rate={s['unit_pass_rate']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
