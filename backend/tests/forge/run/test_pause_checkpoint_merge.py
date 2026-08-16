from app.enums import PauseReason
from app.forge.reliability.pause import merge_pause_checkpoint


def test_merge_preserves_art_and_code_progress() -> None:
    existing = {
        "phase": "code",
        "design_doc": {"title": "t"},
        "art_options": {"options": [1]},
        "attempt": 2,
        "artifacts": ["a"],
    }
    out = merge_pause_checkpoint(
        existing,
        phase="user_pause",
        pause_reason=PauseReason.MANUAL_HOLD,
    )
    assert out["art_options"] == {"options": [1]}
    assert out["attempt"] == 2
    assert out["artifacts"] == ["a"]
    assert out["phase"] == "user_pause"
    assert out["pause_reason"] == PauseReason.MANUAL_HOLD.value
    assert out["design_doc"] == {"title": "t"}
    assert "recovery" not in out
