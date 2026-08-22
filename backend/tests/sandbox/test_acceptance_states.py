"""game_states 静态引用检查。"""

from __future__ import annotations

from app.sandbox.acceptance_states import (
    cheat_probe_state_ids,
    missing_required_state_ids,
    required_state_source_errors,
)


def test_missing_required_state_ids() -> None:
    doc = {
        "title": "t",
        "game_states": [{"id": "menu"}, {"id": "playing"}],
    }
    missing = missing_required_state_ids(doc)
    assert "game_over" in missing
    assert "menu" not in missing


def test_required_state_source_errors() -> None:
    doc = {
        "title": "t",
        "game_states": [
            {"id": "menu"},
            {"id": "playing"},
            {"id": "paused"},
            {"id": "level_complete"},
            {"id": "game_over"},
            {"id": "victory"},
        ],
    }
    html = "<script>menu playing paused level_complete game_over victory</script>"
    assert required_state_source_errors(html, doc) == []


def test_cheat_probe_state_ids() -> None:
    doc = {
        "title": "t",
        "game_states": [{"id": "playing"}, {"id": "game_over"}],
    }
    assert cheat_probe_state_ids(doc) == ["game_over"]
