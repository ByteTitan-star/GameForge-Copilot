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
    """判断是否经 ContextBuilder 拼装节点上下文（恒为 True）。

    场景：测试/兼容旧调用点；正式 Node 一律走 ContextBuilder。
    参数：无。
    返回：恒为 True；回滚粒度改为关闭单项 Memory 能力而非回退手写 concat。
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
    """从 DB 加载摘要/偏好/消息并调用 ContextBuilder 拼装上下文。

    场景：正式节点唯一拼装入口，禁止节点内自行拼历史/偏好。
    参数：
        db - 异步数据库会话；
        node - 当前节点名；
        game - 游戏实体；
        user_id - 用户 ID；
        current_input - 本轮用户输入；
        design_doc - 可选设计稿 dict；
        recent_limit - 近期消息条数上限。
    返回：BuiltContext，含 user_message 与各 section。
    """
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
    """判断该游戏是否应刷新 Session Summary（兼容旧调用点）。

    场景：消息写入后由 graph/loader 触发摘要刷新判断。
    参数：db - 异步数据库会话；game_id - 游戏 ID。
    返回：True 表示消息量或 token 超阈，应刷新摘要。
    """
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
