from app.forge.hitl import HITL_PHASES, allowed_decisions_for, is_hitl_phase


def test_hitl_phases_cover_confirm_and_failures() -> None:
    assert frozenset({"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"}) == HITL_PHASES


def test_allowed_decisions() -> None:
    assert allowed_decisions_for("plan_confirm") == frozenset({"approve", "modify"})
    assert "select_a" in allowed_decisions_for("art_confirm")


def test_is_hitl_phase() -> None:
    assert is_hitl_phase("plan_confirm")
    assert not is_hitl_phase("user_pause")
