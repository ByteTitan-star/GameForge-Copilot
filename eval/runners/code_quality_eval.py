"""Dimension 2: Code quality & QA loop effectiveness.

Issue: #116

Modes:
  - static_baseline: structure/empty heuristics on curated snippets
  - live_derived: QA-loop metrics from enriched generation_eval JSON
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
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
from eval.runners.telemetry import is_empty_or_trivial_html

setup_backend_path()
from app.forge.llm_continuation import has_incomplete_structure  # noqa: E402


def summarize_live_derived(per_run: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate QA/playtest metrics from enriched generation per_run rows."""
    n = max(1, len(per_run))
    final_pass = 0
    first_fail = 0
    repaired = 0
    repair_rounds: list[int] = []
    empty = 0
    cats: Counter[str] = Counter()

    for row in per_run:
        qa = row.get("qa") or {}
        artifact = row.get("artifact") or {}
        if qa.get("final_pass") or row.get("success"):
            final_pass += 1
        if qa.get("first_pass") is False:
            first_fail += 1
            if qa.get("final_pass"):
                repaired += 1
        repair_rounds.append(int(qa.get("repair_rounds") or 0))
        if artifact.get("empty_or_trivial"):
            empty += 1
        for cat in qa.get("error_categories") or []:
            cats[str(cat)] += 1

    return {
        "prompts_run": len(per_run),
        "playtest_pass_rate": round(final_pass / n, 4),
        "repair_effectiveness": round(repaired / first_fail, 4) if first_fail else 1.0,
        "avg_repair_rounds": round(sum(repair_rounds) / n, 4),
        "max_repair_rounds": max(repair_rounds) if repair_rounds else 0,
        "empty_output_rate": round(empty / n, 4),
        "error_category_distribution": dict(cats),
        "mode": "live_derived",
    }


def _latest_generation_report(path: Path | None = None) -> dict[str, Any] | None:
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    reports_dir = _REPO_ROOT / "eval" / "reports"
    candidates = sorted(reports_dir.glob("*_generation_eval.json"), reverse=True)
    for candidate in candidates:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        per_run = data.get("per_run") or []
        if per_run and isinstance(per_run[0], dict) and "qa" in per_run[0]:
            return data
    return None


def _run_static_baseline() -> dict[str, Any]:
    cases = load_dataset("code_quality_samples.json")
    per_case: list[dict[str, Any]] = []
    complete_ok = 0
    empty_ok = 0

    for case in cases:
        html = case["html"]
        actual_complete = not has_incomplete_structure(html)
        actual_empty = is_empty_or_trivial_html(html)
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
    return {
        "sample_count": len(cases),
        "structure_detection_accuracy": round(complete_ok / n, 4),
        "empty_output_detection_accuracy": round(empty_ok / n, 4),
        "empty_labeled_rate": round(
            sum(1 for c in per_case if c["expected_empty"]) / n, 4
        ),
        "mode": "static_baseline",
        "per_case": per_case,
    }


def run_eval(*, from_generation: Path | None = None) -> dict[str, Any]:
    static = _run_static_baseline()
    report = base_report_meta(
        dimension="code_quality",
        runner="eval/runners/code_quality_eval.py",
        mode=static["mode"],
    )
    report["summary"] = {
        "sample_count": static["sample_count"],
        "structure_detection_accuracy": static["structure_detection_accuracy"],
        "empty_output_detection_accuracy": static["empty_output_detection_accuracy"],
        "empty_labeled_rate": static["empty_labeled_rate"],
        "mode": static["mode"],
    }
    report["per_case"] = static["per_case"]

    gen = _latest_generation_report(from_generation)
    if gen is not None:
        live = summarize_live_derived(list(gen.get("per_run") or []))
        report["live_derived"] = live
        report["summary"]["live_derived"] = live
        report["summary"]["mode"] = "static_baseline+live_derived"
        report["mode"] = "static_baseline+live_derived"
        report["note"] = (
            "Static baseline plus live_derived QA metrics from generation_eval JSON."
        )
    else:
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
        mode=str(s.get("mode") or report.get("mode")),
        sha=sha,
        ts=ts,
    )
    lines += [
        f"| structure_detection_accuracy | {s['structure_detection_accuracy']:.1%} | >= 90% | "
        f"{status_cell(s['structure_detection_accuracy'], 0.90, higher_is_better=True)} |",
        f"| empty_output_detection_accuracy | {s['empty_output_detection_accuracy']:.1%} | >= 90% | "
        f"{status_cell(s['empty_output_detection_accuracy'], 0.90, higher_is_better=True)} |",
        f"| empty_labeled_rate (dataset) | {s.get('empty_labeled_rate', 0):.1%} | informational | — |",
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

    live = report.get("live_derived") or s.get("live_derived")
    if live:
        lines += [
            "",
            "## 5. Live-derived QA metrics",
            "",
            f"| playtest_pass_rate | {live['playtest_pass_rate']:.1%} | >= 90% | "
            f"{status_cell(live['playtest_pass_rate'], 0.90, higher_is_better=True)} |",
            f"| repair_effectiveness | {live['repair_effectiveness']:.1%} | >= 70% | "
            f"{status_cell(live['repair_effectiveness'], 0.70, higher_is_better=True)} |",
            f"| avg_repair_rounds | {live['avg_repair_rounds']} | <= 2.0 | "
            f"{'✅' if live['avg_repair_rounds'] <= 2.0 else '❌'} |",
            f"| max_repair_rounds | {live['max_repair_rounds']} | tracked | — |",
            f"| empty_output_rate | {live['empty_output_rate']:.1%} | <= 5% | "
            f"{status_cell(live['empty_output_rate'], 0.05, higher_is_better=False)} |",
            "",
            "### Error category distribution",
            "",
        ]
        dist = live.get("error_category_distribution") or {}
        if dist:
            for k, v in sorted(dist.items()):
                lines.append(f"- `{k}`: {v}")
        else:
            lines.append("- (none)")

    below: list[str] = []
    if s["structure_detection_accuracy"] < 0.90:
        below.append("- structure_detection_accuracy below 90% in static mode")
    if s["empty_output_detection_accuracy"] < 0.90:
        below.append("- empty_output_detection_accuracy below 90% in static mode")
    if live:
        if live["playtest_pass_rate"] < 0.90:
            below.append(f"- playtest_pass_rate {live['playtest_pass_rate']:.1%} below 90%")
        if live["repair_effectiveness"] < 0.70:
            below.append(
                f"- repair_effectiveness {live['repair_effectiveness']:.1%} below 70%"
            )
        if live["empty_output_rate"] > 0.05:
            below.append(f"- empty_output_rate {live['empty_output_rate']:.1%} above 5%")
    lines.append("")
    lines.extend(below_target_section(below))
    lines += [
        "## 7. Conclusion",
        "",
        report.get("note") or "",
        "",
    ]
    return write_markdown(DOCS_EVALS_DIR / "code-quality-eval-report.md", lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Code quality / QA loop eval")
    parser.add_argument(
        "--from-generation",
        type=Path,
        default=None,
        help="Path to enriched *_generation_eval.json",
    )
    args = parser.parse_args()
    from_gen = args.from_generation
    if from_gen is None:
        env_path = os.environ.get("EVAL_FROM_GENERATION", "").strip()
        if env_path:
            from_gen = Path(env_path)

    report = run_eval(from_generation=from_gen)
    json_path = write_json_report("code_quality_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"structure_detection_accuracy={s['structure_detection_accuracy']:.1%}")
    if s.get("live_derived"):
        print(f"playtest_pass_rate={s['live_derived']['playtest_pass_rate']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
