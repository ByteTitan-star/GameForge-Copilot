"""Checkpoint 瘦身：有 revision id 时不持久化大 payload；兼容胖状态。"""

from __future__ import annotations

from app.forge.checkpoint_slim import slim_checkpoint_payloads


def test_slim_drops_design_doc_when_plan_revision_present() -> None:
    state = {
        "phase": "plan_confirm",
        "design_doc": {"title": "跑酷", "gameplay": "..."},
        "active_plan_revision_id": "11111111-1111-1111-1111-111111111111",
        "pause_reason": "waiting_user",
    }
    out = slim_checkpoint_payloads(state)
    assert "design_doc" not in out
    assert out["active_plan_revision_id"] == state["active_plan_revision_id"]
    assert out["phase"] == "plan_confirm"


def test_slim_keeps_design_doc_without_revision_id() -> None:
    state = {
        "phase": "plan_confirm",
        "design_doc": {"title": "跑酷"},
        "pause_reason": "waiting_user",
    }
    out = slim_checkpoint_payloads(state)
    assert out["design_doc"] == {"title": "跑酷"}


def test_slim_drops_art_direction_when_art_revision_present() -> None:
    state = {
        "phase": "art_detail",
        "art_direction": {"style": "pixel"},
        "active_art_revision_id": "22222222-2222-2222-2222-222222222222",
        "art_options": {"options": [{"id": "a"}]},
    }
    out = slim_checkpoint_payloads(state)
    assert "art_direction" not in out
    assert out["art_options"] == {"options": [{"id": "a"}]}
    assert out["active_art_revision_id"] == state["active_art_revision_id"]


def test_slim_is_idempotent_on_already_slim_state() -> None:
    state = {
        "phase": "plan_confirm",
        "active_plan_revision_id": "11111111-1111-1111-1111-111111111111",
    }
    assert slim_checkpoint_payloads(state) == state
