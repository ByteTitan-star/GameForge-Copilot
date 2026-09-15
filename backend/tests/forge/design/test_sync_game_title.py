"""plan 产物副作用（_finish_plan）把 design_doc.title 同步到 Game.title（ADR-18）。

标题同步原在 plan_confirm 暂停时提交；确认门取消后迁移到 plan 节点尾部。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.enums import RunStatus
from app.forge.graph import _Ctx, _finish_plan


def _make_ctx(game: MagicMock) -> _Ctx:
    run = MagicMock()
    run.id = uuid4()
    run.user_id = uuid4()
    run.status = RunStatus.RUNNING.value
    run.ended_at = None

    session = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    session.add = MagicMock()

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    return _Ctx(s=session, r=mock_redis, run=run, game=game)


def _patch_finish_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.forge.graph.ckpt.load_state", AsyncMock(return_value={}))
    monkeypatch.setattr(
        "app.forge.graph.hydrate_checkpoint_payloads",
        AsyncMock(side_effect=lambda _s, st: st),
    )
    monkeypatch.setattr("app.forge.graph.ckpt.save_state", AsyncMock())
    monkeypatch.setattr("app.forge.graph.add_message", AsyncMock())
    monkeypatch.setattr("app.forge.graph.slim_checkpoint_payloads", lambda ck: ck)
    monkeypatch.setattr(
        "app.forge.graph.side_effect_key", lambda *args, **kwargs: "key"
    )
    monkeypatch.setattr(
        "app.forge.graph.try_begin_side_effect", AsyncMock(return_value=True)
    )
    plan_row = MagicMock()
    plan_row.id = uuid4()
    monkeypatch.setattr(
        "app.forge.graph.ensure_plan_revision",
        AsyncMock(return_value=(plan_row, False, False)),
    )


@pytest.mark.asyncio
async def test_finish_plan_syncs_game_title(monkeypatch: pytest.MonkeyPatch) -> None:
    game = MagicMock()
    game.id = uuid4()
    game.title = "制作一个简化资源管理游戏"
    ctx = _make_ctx(game)
    _patch_finish_plan(monkeypatch)

    doc = {"title": "Isle Manager: 孤岛经营", "gameplay": "x"}
    await _finish_plan(ctx, doc, force_new_plan=False)

    assert game.title == "Isle Manager: 孤岛经营"
    ctx.s.add.assert_called_with(game)
    ctx.s.commit.assert_awaited()


@pytest.mark.asyncio
async def test_finish_plan_without_title_keeps_game_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    game = MagicMock()
    game.id = uuid4()
    game.title = "Keep Me"
    ctx = _make_ctx(game)
    _patch_finish_plan(monkeypatch)

    await _finish_plan(ctx, {"gameplay": "无标题稿"}, force_new_plan=False)

    assert game.title == "Keep Me"
