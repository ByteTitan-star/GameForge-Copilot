"""从 DB 装配 ContextBuilder 输入（P1）。"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.forge.memory.context_builder import (
    BuiltContext,
    ContextArtifacts,
    ContextBuilder,
    ContextTurn,
    estimate_tokens,
)
from app.forge.memory.preferences import list_active_preferences, preference_to_context_dict
from app.forge.memory.summary import coerce_session_summary
from app.models.forge_message import ForgeMessage
from app.models.game import Game


async def build_node_context(
    db: AsyncSession,
    *,
    node: str,
    game: Game,
    user_id: uuid.UUID,
    current_input: str,
    design_doc: dict | None = None,
    recent_limit: int = 12,
) -> BuiltContext:
    """规范路径：新节点应经此入口拼装，而非自行拼历史。"""
    summary = coerce_session_summary(game.session_summary_json)
    prefs: list[dict] = []
    if settings.memory_preferences:
        rows = await list_active_preferences(db, user_id)
        prefs = [preference_to_context_dict(r) for r in rows]

    turns: list[ContextTurn] = []
    if settings.memory_context_builder:
        msg_rows = (
            await db.scalars(
                select(ForgeMessage)
                .where(ForgeMessage.game_id == game.id)
                .order_by(ForgeMessage.created_at.desc(), ForgeMessage.id.desc())
                .limit(recent_limit)
            )
        ).all()
        turns = [
            ContextTurn(role=m.role, content=m.content)
            for m in reversed(list(msg_rows))
        ]

    artifacts = ContextArtifacts(design_doc=design_doc) if design_doc else ContextArtifacts()
    return ContextBuilder.build(
        node=node,
        current_input=current_input,
        session_summary=dict(summary) if summary else None,
        recent_turns=turns,
        preferences=prefs,
        artifacts=artifacts,
        budget_tokens=settings.memory_context_budget_tokens,
    )


async def maybe_touch_session_summary_flag(db: AsyncSession, game_id: uuid.UUID) -> bool:
    """若消息量超阈返回 True（调用方再决定是否跑 LLM 摘要；P1 MVP 只暴露触发条件）。"""
    count = await db.scalar(
        select(func.count()).select_from(ForgeMessage).where(ForgeMessage.game_id == game_id)
    ) or 0
    # 粗估：取最近 50 条内容长度
    rows = (
        await db.scalars(
            select(ForgeMessage.content)
            .where(ForgeMessage.game_id == game_id)
            .order_by(ForgeMessage.created_at.desc())
            .limit(50)
        )
    ).all()
    tokens = sum(estimate_tokens(c or "") for c in rows)
    from app.forge.memory.summary import should_refresh_summary

    return should_refresh_summary(message_count=int(count), historical_tokens=tokens)
