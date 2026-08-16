"""P1：Session Summary 持久化刷新。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.forge.memory.refresh import refresh_session_summary_if_needed
from app.forge.messages import add_message
from app.models.game import Game
from app.models.user import User


@pytest.mark.asyncio
async def test_refresh_persists_summary_when_forced(db_session) -> None:
    user = User(
        id=uuid4(),
        email=f"sum-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    game = Game(
        id=uuid4(),
        owner_id=user.id,
        title="摘要游戏",
        requirement="初始需求",
    )
    db_session.add_all([user, game])
    await db_session.flush()
    await add_message(
        db_session,
        game_id=game.id,
        run_id=None,
        user_id=user.id,
        role="user",
        kind="requirement",
        content="做一个像素风跑酷",
    )
    await db_session.commit()

    summary = await refresh_session_summary_if_needed(db_session, game, force=True)
    await db_session.commit()

    assert summary is not None
    assert "跑酷" in summary["current_goal"] or "像素" in summary["current_goal"]
    row = await db_session.scalar(select(Game).where(Game.id == game.id))
    assert row is not None
    assert row.session_summary_json is not None
    assert row.session_summary_json.get("current_goal")


@pytest.mark.asyncio
async def test_refresh_skipped_below_threshold(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.forge.memory.refresh.settings.memory_session_summary", True
    )
    user = User(
        id=uuid4(),
        email=f"sum2-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    game = Game(
        id=uuid4(),
        owner_id=user.id,
        title="短对话",
        requirement="短",
    )
    db_session.add_all([user, game])
    await db_session.flush()
    await add_message(
        db_session,
        game_id=game.id,
        run_id=None,
        user_id=user.id,
        role="user",
        kind="requirement",
        content="一句话",
    )
    await db_session.commit()

    out = await refresh_session_summary_if_needed(db_session, game, force=False)
    assert out is None or game.session_summary_json is None
