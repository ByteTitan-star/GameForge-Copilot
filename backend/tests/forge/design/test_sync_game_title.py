"""plan_confirm 暂停时把 design_doc.title 同步到 Game.title。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.enums import RunStatus
from app.forge.graph import _Ctx, _pause_hitl


@pytest.mark.asyncio
async def test_pause_plan_confirm_syncs_game_title(monkeypatch: pytest.MonkeyPatch) -> None:
    game = MagicMock()
    game.id = uuid4()
    game.title = "制作一个简化资源管理游戏"

    run = MagicMock()
    run.id = uuid4()
    run.user_id = uuid4()
    run.status = RunStatus.RUNNING.value
    run.ended_at = None

    session = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    ctx = _Ctx(s=session, r=MagicMock(), run=run, game=game)
    design_doc = {"title": "Isle Manager: 孤岛经营", "gameplay": "x"}

    monkeypatch.setattr("app.forge.graph.apply_paused_metadata", lambda _run: None)
    monkeypatch.setattr(
        "app.forge.graph.ckpt.load_state",
        AsyncMock(return_value={"phase": "plan_confirm"}),
    )
    monkeypatch.setattr("app.forge.graph.ckpt.save_state", AsyncMock())
    monkeypatch.setattr("app.forge.graph.add_message", AsyncMock())
    monkeypatch.setattr("app.forge.graph.publish_event", AsyncMock())
    monkeypatch.setattr(
        "app.forge.graph.build_pause_checkpoint",
        lambda **kwargs: {"phase": kwargs["phase"], "design_doc": kwargs["design_doc"]},
    )
    monkeypatch.setattr("app.forge.graph.design_message_content", lambda _doc: "msg")
    monkeypatch.setattr("app.forge.graph.stable_design_key", lambda *_a, **_k: "k")

    await _pause_hitl(ctx, "plan_confirm", design_doc)

    assert game.title == "Isle Manager: 孤岛经营"
    session.add.assert_called_with(game)
    session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_pause_art_confirm_does_not_sync_title(monkeypatch: pytest.MonkeyPatch) -> None:
    game = MagicMock()
    game.id = uuid4()
    game.title = "Keep Me"

    run = MagicMock()
    run.id = uuid4()
    run.user_id = uuid4()
    run.status = RunStatus.RUNNING.value
    run.ended_at = None

    session = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()

    ctx = _Ctx(s=session, r=MagicMock(), run=run, game=game)
    design_doc = {"title": "Should Not Apply: 不该覆盖", "gameplay": "x"}

    monkeypatch.setattr("app.forge.graph.apply_paused_metadata", lambda _run: None)
    monkeypatch.setattr("app.forge.graph.ckpt.load_state", AsyncMock(return_value={}))
    monkeypatch.setattr("app.forge.graph.ckpt.save_state", AsyncMock())
    monkeypatch.setattr("app.forge.graph.add_message", AsyncMock())
    monkeypatch.setattr("app.forge.graph.publish_event", AsyncMock())
    monkeypatch.setattr(
        "app.forge.graph.build_pause_checkpoint",
        lambda **kwargs: {"phase": kwargs["phase"], "design_doc": kwargs["design_doc"]},
    )
    monkeypatch.setattr("app.forge.graph.design_message_content", lambda _doc: "msg")
    monkeypatch.setattr("app.forge.graph.stable_design_key", lambda *_a, **_k: "k")

    await _pause_hitl(ctx, "art_confirm", design_doc)

    assert game.title == "Keep Me"
