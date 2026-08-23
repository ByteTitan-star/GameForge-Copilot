"""Session Summary 持久化刷新（P1）。"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.forge.memory.context_builder import ContextTurn, estimate_tokens
from app.forge.memory.summary import (
    SessionSummary,
    coerce_session_summary,
    should_refresh_summary,
    synthesize_summary_from_turns,
)
from app.models.forge_message import ForgeMessage
from app.models.game import Game

Summarizer = Callable[[list[ContextTurn], SessionSummary | None], Awaitable[SessionSummary]]


async def load_recent_turns(
    db: AsyncSession, game_id: uuid.UUID, *, limit: int = 50
) -> list[ContextTurn]:
    """从 DB 加载游戏近期 ForgeMessage 并转为 ContextTurn 列表。

    场景：``refresh_session_summary_if_needed`` 收集对话轮次。
    参数：db - 异步数据库会话；game_id - 游戏 ID；limit - 最多条数。
    返回：按时间正序的 ContextTurn 列表。
    """
    rows = (
        await db.scalars(
            select(ForgeMessage)
            .where(ForgeMessage.game_id == game_id)
            .order_by(ForgeMessage.created_at.desc(), ForgeMessage.id.desc())
            .limit(limit)
        )
    ).all()
    return [ContextTurn(role=m.role, content=m.content) for m in reversed(list(rows))]


async def refresh_session_summary_if_needed(
    db: AsyncSession,
    game: Game,
    *,
    summarizer: Summarizer | None = None,
    force: bool = False,
) -> SessionSummary | None:
    """超阈或 force 时刷新 Session Summary 并写回 game.session_summary_json。

    场景：消息累积后异步刷新摘要；可注入 LLM summarizer 增强。
    参数：
        db - 异步数据库会话；
        game - 游戏实体；
        summarizer - 可选异步摘要函数；
        force - 是否强制刷新（忽略阈值）。
    返回：刷新后的 SessionSummary；未刷新时返回已有摘要。
    """
    if not settings.memory_session_summary and not force:
        return coerce_session_summary(game.session_summary_json)

    turns = await load_recent_turns(db, game.id)
    count = (
        await db.scalar(
            select(func.count()).select_from(ForgeMessage).where(ForgeMessage.game_id == game.id)
        )
        or 0
    )
    tokens = sum(estimate_tokens(t.content) for t in turns)
    if not force and not should_refresh_summary(message_count=int(count), historical_tokens=tokens):
        return coerce_session_summary(game.session_summary_json)

    previous = coerce_session_summary(game.session_summary_json)
    if summarizer is not None:
        summary = await summarizer(turns, previous)
    else:
        summary = synthesize_summary_from_turns(turns, previous=previous)
    coerced = coerce_session_summary(dict(summary)) or synthesize_summary_from_turns(
        turns, previous=previous
    )
    game.session_summary_json = dict(coerced)
    await db.flush()
    return coerced
