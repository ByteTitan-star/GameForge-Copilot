"""Dimension 7: User preference persistence eval (context injection baseline).

Issue: #124

Validates that explicit preferences are formatted and injected into ContextBuilder
output. Full DB cross-session tests require live API + PostgreSQL.
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
from app.forge.memory.context_builder import ContextBuilder  # noqa: E402


def run_eval() -> dict[str, Any]:
    scenarios = load_dataset("preference_scenarios.json")
    per_case: list[dict[str, Any]] = []
    injection_ok = 0
    explicit_ok = 0

    for sc in scenarios:
        prefs = [
            {
                "category": p["category"],
                "key": p["key"],
                "value_json": p["value_json"],
                "source": p["source"],
            }
            for p in sc["expected_preferences"]
        ]
        built = ContextBuilder.build(
            node="plan",
            current_input=sc["session2_prompt"],
            session_summary=None,
            recent_turns=[],
            preferences=prefs,
            artifacts=None,
            budget_tokens=4096,
        )
        body = built.user_message
        expected_keys = sc.get("expected_in_prompt") or []
        found = [k for k in expected_keys if k.split(".")[0] in body and k.split(".")[-1] in body]
        explicit_count = sum(1 for p in prefs if p.get("source") == "explicit")
        explicit_found = len(found)
        case_ok = explicit_found == len(expected_keys)
        if case_ok:
            injection_ok += 1
        if explicit_count == 0 or explicit_found >= explicit_count:
            explicit_ok += 1
        per_case.append(
            {
                "id": sc["id"],
                "expected_in_prompt": expected_keys,
                "found": found,
                "injection_ok": case_ok,
                "has_preferences_section": "Explicit Preferences" in body,
            }
        )

    n = max(1, len(scenarios))
    summary = {
        "scenario_count": len(scenarios),
        "cross_session_injection_rate": round(injection_ok / n, 4),
        "explicit_extraction_accuracy": round(explicit_ok / n, 4),
        "mode": "context_builder_baseline",
    }

    report = base_report_meta(
        dimension="preference_persistence",
        runner="eval/runners/preference_eval.py",
        mode=summary["mode"],
    )
    report["summary"] = summary
    report["per_case"] = per_case
    report["note"] = (
        "Implicit extraction and DB persistence require live LLM + PostgreSQL. "
        "This baseline validates prompt injection formatting only."
    )
    return report


def write_markdown_report(report: dict[str, Any]) -> Path:
    s = report["summary"]
    ts = report["timestamp"]
    sha = report["git_sha"]
    lines = report_header(
        title="User Preference Persistence Eval Report",
        summary=(
            f"Context injection baseline on **{s['scenario_count']}** scenarios. "
            f"Cross-session injection rate: **{s['cross_session_injection_rate']:.1%}**."
        ),
        runner="eval/runners/preference_eval.py",
        dataset="eval/datasets/preference_scenarios.json",
        dataset_count=s["scenario_count"],
        mode=s["mode"],
        sha=sha,
        ts=ts,
    )
    lines += [
        f"| cross_session_injection_rate | {s['cross_session_injection_rate']:.1%} | 100% | "
        f"{status_cell(s['cross_session_injection_rate'], 1.0, higher_is_better=True)} |",
        f"| explicit_extraction_accuracy | {s['explicit_extraction_accuracy']:.1%} | >= 95% | "
        f"{status_cell(s['explicit_extraction_accuracy'], 0.95, higher_is_better=True)} |",
        "",
        "## 7. Conclusion",
        "",
        report["note"],
        "",
    ]
    lines.extend(
        below_target_section(
            [
                "- cross_session_injection_rate below 100% in context builder baseline"
                if s["cross_session_injection_rate"] < 1.0
                else ""
            ]
        )
    )
    return write_markdown(DOCS_EVALS_DIR / "preference-eval-report.md", lines)


def main() -> None:
    report = run_eval()
    json_path = write_json_report("preference_eval", report)
    md_path = write_markdown_report(report)
    s = report["summary"]
    print(f"cross_session_injection_rate={s['cross_session_injection_rate']:.1%}")
    print(f"JSON: {json_path}")
    print(f"MD:   {md_path}")


if __name__ == "__main__":
    main()
