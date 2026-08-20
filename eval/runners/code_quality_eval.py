"""Dimension 2: Code quality & QA loop effectiveness (static baseline).

Issue: #116

Measures structural completeness heuristics on curated HTML/JSON snippets
using `has_incomplete_structure()` — no live Playwright or LLM required.

Live end-to-end QA metrics are derived from `generation_eval` JSON when present.
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
from app.forge.llm_continuation import has_incomplete_structure  # noqa: E402


def _is_empty_output(html: str) -> bool:
    text = html.strip()
    if not text:
        return True
    if text in {"<html></html>", "<html><body></body></html>"}:
        return True
    if "<body>" in text.lower() and len(text) < 40:
        return True
    return False


def run_eval() -> dict[str, Any]:
    cases = load_dataset("code_quality_samples.json")
    per_case: list[dict[str, Any]] = []
    complete_ok = 0
    empty_ok = 0

    for case in cases:
        html = case["html"]
        actual_complete = not has_incomplete_structure(html)
        actual_empty = _is_empty_output(html)
        complete_match = actual_complete == case["expected_complete"]
        empty_match = actual_empty == case["expected_empty"]
        if complete_match:
            complete_ok += 1
        if empty_match:
            empty_ok += 1
        per_case.append(
            {
                "id": case["id"],
                "expected_complete": case["expected_complete"],
                "actual_complete": actual_complete,
                "expected_empty": case["expected_empty"],
                "actual_empty": actual_empty,
                "complete_match": complete_match,
                "empty_match": empty_match,
            }
        )

    n = max(1, len(cases))
    summary = {
        "sample_count": len(cases),
        "structure_detection_accuracy": round(complete_ok / n, 4),
        "empty_output_detection_accuracy": round(empty_ok / n, 4),
        "empty_output_rate": round(
            sum(1 for c in per_case if c["actual_empty"]) / n, 4
        ),
        "mode": "static_baseline",
    }

    report = base_report_meta(
        dimension="code_quality",
        runner="eval/runners/code_quality_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["per_case"] = per_case
    report["note"] = (
        "Playtest pass rate and repair effectiveness require live generation runs "
        "(see generation_eval --live)."
    )
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="Code Quality & QA Loop Eval Report",
        summary=(
            f"Static structural analysis on **{s['sample_count']}** curated snippets. "
            f"Structure detection accuracy: **{s['structure_detection_accuracy']:.1%}**, "
            f"empty-output detection: **{s['empty_output_detection_accuracy']:.1%}**."
        ),
        runner="eval/runners/code_quality_eval.py",
        dataset="eval/datasets/code_quality_samples.json",
        dataset_count=s["sample_count"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    lines += [
        f"| structure_detection_accuracy | {s['structure_detection_accuracy']:.1%} | >= 90% | "
        f"{status_cell(s['structure_detection_accuracy'], 0.90, higher_is_better=True)} |",
        f"| empty_output_detection_accuracy | {s['empty_output_detection_accuracy']:.1%} | >= 90% | "
        f"{status_cell(s['empty_output_detection_accuracy'], 0.90, higher_is_better=True)} |",
        f"| empty_output_rate (samples) | {s['empty_output_rate']:.1%} | <= 5% | "
        f"{status_cell(s['empty_output_rate'], 0.05, higher_is_better=False)} |",
        "",
        "## 4. Failure Analysis",
        "",
    ]
    failures = [c for c in report["per_case"] if not c["complete_match"] or not c["empty_match"]]
    if failures:
        lines.append("| id | complete_match | empty_match |")
        lines.append("|---|---|---|")
        for f in failures:
            lines.append(f"| {f['id']} | {f['complete_match']} | {f['empty_match']} |")
    else:
        lines.append("No static baseline failures.")
    lines.append("")
    lines.extend(
        below_target_section(
            [
                f"- **structure_detection_accuracy** below 90% in static mode"
                if s["structure_detection_accuracy"] < 0.90
                else "",
            ]
        )
    )
    lines += [
        "## 7. Conclusion",
        "",
        report["note"],
        "",
    ]
    return write_markdown(DOCS_EVALS_DIR / "code-quality-eval-report.md", lines)


def main() -> None:
    report = run_eval()
    json_path = write_json_report("code_quality_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"structure_detection_accuracy={s['structure_detection_accuracy']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
