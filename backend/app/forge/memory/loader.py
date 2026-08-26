"""从 DB 装配 ContextBuilder 输入（P1）；P5 为正式 Node 唯一拼装入口。"""

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
from app.forge.memory.summary import coerce_session_summary, should_refresh_summary
from app.models.forge_message import ForgeMessage
from app.models.game import Game


def use_context_builder() -> bool:
    """正式 Node 一律经 ContextBuilder；保留函数供测试/兼容，恒为 True。

    回滚粒度改为关闭单项 Memory 能力（summary / preferences / recent turns），
    不再回退到节点内手写 concat。
    """
    return True


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
    """规范路径：正式节点必须经此入口拼装，禁止自行拼历史/偏好。"""
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
        turns = [ContextTurn(role=m.role, content=m.content) for m in reversed(list(msg_rows))]

    artifacts = ContextArtifacts(design_doc=design_doc) if design_doc else ContextArtifacts()

    retrieved: list = []
    knowledge_cap = 0
    if settings.knowledge_rag_enabled:
        from app.forge.knowledge.retriever import retrieve_knowledge_for_node

        retrieved = await retrieve_knowledge_for_node(
            node=node,
            current_input=current_input,
            design_doc=design_doc,
        )
        knowledge_cap = settings.knowledge_token_budget

    from app.forge.tracing import observe_context_build, observe_subsystem

    with observe_subsystem("memory", "build_node_context", metadata={"node": node}):
        built = ContextBuilder.build(
            node=node,
            current_input=current_input,
            session_summary=dict(summary) if summary else None,
            recent_turns=turns,
            preferences=prefs,
            artifacts=artifacts,
            budget_tokens=settings.memory_context_budget_tokens,
            retrieved_knowledge=retrieved or None,
            knowledge_token_cap=knowledge_cap,
        )
        section_lens = {k: len(v or "") for k, v in built.sections.items()}
        with observe_context_build(
            node=built.node,
            token_estimate=built.token_estimate,
            fingerprint=built.fingerprint,
            section_lens=section_lens,
        ):
            pass
    return built


async def maybe_touch_session_summary_flag(db: AsyncSession, game_id: uuid.UUID) -> bool:
    """若消息量超阈返回 True（兼容旧调用点）。"""
    count = (
        await db.scalar(
            select(func.count()).select_from(ForgeMessage).where(ForgeMessage.game_id == game_id)
        )
        or 0
    )
    rows = (
        await db.scalars(
            select(ForgeMessage.content)
            .where(ForgeMessage.game_id == game_id)
            .order_by(ForgeMessage.created_at.desc())
            .limit(50)
        )
    ).all()
    tokens = sum(estimate_tokens(c or "") for c in rows)
    return should_refresh_summary(message_count=int(count), historical_tokens=tokens)
