"""Unit tests for code quality live_derived aggregation (#116)."""

from eval.runners.code_quality_eval import summarize_live_derived


def test_summarize_live_derived_basic() -> None:
    per_run = [
        {
            "id": "gen-001",
            "success": True,
            "qa": {
                "attempts": 1,
                "first_pass": True,
                "final_pass": True,
                "repair_rounds": 0,
                "error_categories": [],
            },
            "artifact": {"empty_or_trivial": False},
        },
        {
            "id": "gen-002",
            "success": True,
            "qa": {
                "attempts": 2,
                "first_pass": False,
                "final_pass": True,
                "repair_rounds": 1,
                "error_categories": ["runtime"],
            },
            "artifact": {"empty_or_trivial": False},
        },
    ]
    s = summarize_live_derived(per_run)
    assert s["playtest_pass_rate"] == 1.0
    assert s["repair_effectiveness"] == 1.0
    assert s["avg_repair_rounds"] == 0.5
    assert s["empty_output_rate"] == 0.0
    assert s["error_category_distribution"]["runtime"] == 1
    assert s["prompts_run"] == 2
