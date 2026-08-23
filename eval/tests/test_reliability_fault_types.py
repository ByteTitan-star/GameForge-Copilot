"""Unit tests for reliability fault case routing (#125)."""

from eval.runners.reliability_eval import is_live_fault_case, is_unit_case


def test_case_routing() -> None:
    assert is_unit_case({"type": "truncation_html"})
    assert is_unit_case({"type": "pause_checkpoint_merge"})
    assert is_live_fault_case({"type": "llm_timeout_then_ok"})
    assert is_live_fault_case({"type": "mid_run_kill_resume"})
    assert not is_unit_case({"type": "llm_timeout_then_ok"})
    assert not is_live_fault_case({"type": "truncation_html"})
