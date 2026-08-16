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
    rows = (
        await db.scalars(
            select(ForgeMessage)
            .where(ForgeMessage.game_id == game_id)
            .order_by(ForgeMessage.created_at.desc(), ForgeMessage.id.desc())
            .limit(limit)
        )
    ).all()
    return [
        ContextTurn(role=m.role, content=m.content) for m in reversed(list(rows))
    ]


async def refresh_session_summary_if_needed(
    db: AsyncSession,
    game: Game,
    *,
    summarizer: Summarizer | None = None,
    force: bool = False,
) -> SessionSummary | None:
    """超阈（或 force）时刷新并写回 ``game.session_summary_json``。

    默认用确定性 synthesizer；可注入 async summarizer（例如 LLM）做增强。
    """
    if not settings.memory_session_summary and not force:
        return coerce_session_summary(game.session_summary_json)

    turns = await load_recent_turns(db, game.id)
    count = await db.scalar(
        select(func.count()).select_from(ForgeMessage).where(ForgeMessage.game_id == game.id)
    ) or 0
    tokens = sum(estimate_tokens(t.content) for t in turns)
    if not force and not should_refresh_summary(
        message_count=int(count), historical_tokens=tokens
    ):
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
