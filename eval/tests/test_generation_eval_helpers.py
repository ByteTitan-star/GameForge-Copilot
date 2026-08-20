"""Unit tests for generation live-eval helpers."""

from eval.runners.generation_eval import classify_terminal, hitl_decision_for


def test_hitl_decision_map() -> None:
    assert hitl_decision_for("plan_confirm") == "approve"
    assert hitl_decision_for("art_confirm") == "select_a"
    assert hitl_decision_for("unknown") is None


def test_classify_terminal_success() -> None:
    ok, cat = classify_terminal(
        "done",
        artifact_gate={"generation_success": True, "previewable": True},
    )
    assert ok is True
    assert cat is None


def test_classify_terminal_done_without_artifact() -> None:
    ok, cat = classify_terminal("done", artifact_gate={"generation_success": False})
    assert ok is False
    assert cat == "done_without_artifact"


def test_classify_terminal_failed_and_timeout() -> None:
    ok, cat = classify_terminal("failed", artifact_gate=None)
    assert ok is False and cat == "run_failed"
    ok2, cat2 = classify_terminal("running", artifact_gate=None, timed_out=True)
    assert ok2 is False and cat2 == "timeout"
