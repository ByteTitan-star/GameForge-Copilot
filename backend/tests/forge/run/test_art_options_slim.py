"""art_options revision：有 id 时可从 checkpoint 去掉大 payload。"""

from __future__ import annotations

from app.forge.checkpoint_slim import slim_checkpoint_payloads


def test_slim_drops_art_options_when_revision_present() -> None:
    state = {
        "phase": "art_confirm",
        "art_options": {"options": [{"id": "A"}, {"id": "B"}]},
        "active_art_options_revision_id": "33333333-3333-3333-3333-333333333333",
    }
    out = slim_checkpoint_payloads(state)
    assert "art_options" not in out
    assert out["active_art_options_revision_id"] == state["active_art_options_revision_id"]


def test_slim_keeps_art_options_without_revision() -> None:
    state = {"art_options": {"options": [{"id": "A"}, {"id": "B"}]}}
    assert slim_checkpoint_payloads(state)["art_options"]["options"][0]["id"] == "A"
