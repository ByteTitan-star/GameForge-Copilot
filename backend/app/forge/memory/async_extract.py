"""偏好抽取异步化（ADR-18 follow-up）：移出节点关键路径。

同步抽取在每次 plan/art 组装 prompt 前多一次抽取 LLM 往返（阻塞首字延迟）；
改为 fire-and-forget 后台任务：
- 独立 DB session（任务与请求 session 生命周期解耦）；redis 复用连接池；
- 超时护栏（preference_extract_timeout_s），失败只 log——偏好抽取是
  best-effort 增强，绝不能阻塞或失败 run；
- 内容哈希去重（同 user 同文本 24h 只抽一次；requirement 在每次 resume
  重组装时会重复出现）。重复抽取本身经 Preference Service 合并策略幂等，
  去重仅为省一次 LLM 调用；抽取失败不写去重键，下次同文本仍可重试。

worker 事件循环长期存活，任务跨请求延续；关停时在途任务作废（可接受）。
drain_preference_tasks() 供测试确定性等待。
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid

import redis.asyncio as redis

from app.core.config import settings

log = logging.getLogger(__name__)

_pending: set[asyncio.Task[None]] = set()


def _dedupe_key(user_id: uuid.UUID, text: str) -> str:
    digest = hashlib.sha256(f"{user_id}\0{text}".encode()).hexdigest()[:24]
    return f"pref:extract:dedupe:{digest}"


def schedule_preference_extraction(
    r: redis.Redis,
    user_id: uuid.UUID,
    text: str | None,
    *,
    source: str = "compose",
) -> None:
    """把文本丢给后台抽取任务（非阻塞）；未启用偏好或空文本直接返回。"""
    stripped = (text or "").strip()
    if not stripped or not settings.memory_preferences:
        return
    task = asyncio.create_task(_extract(r, user_id, stripped, source))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def _extract(r: redis.Redis, user_id: uuid.UUID, text: str, source: str) -> None:
    try:
        if await r.get(_dedupe_key(user_id, text)):
            return

        async def _run() -> None:
            from sqlalchemy import select

            from app.core import db as dbmod
            from app.forge.memory.preferences import upsert_preferences_from_text
            from app.models.game import Game

            async with dbmod.SessionLocal() as s:
                history: list[str] = []
                if settings.preference_history_infer_enabled:
                    # 行为信号（ADR-16 增量）：近期需求文本供模型识别反复口味模式
                    rows = (
                        await s.scalars(
                            select(Game.requirement)
                            .where(Game.owner_id == user_id)
                            .order_by(Game.created_at.desc())
                            .limit(settings.preference_history_max_items)
                        )
                    ).all()
                    history = [h for h in rows if h]
                await upsert_preferences_from_text(
                    s, user_id=user_id, text=text, history_texts=history
                )
                await s.commit()

        await asyncio.wait_for(_run(), timeout=settings.preference_extract_timeout_s)
        await r.set(_dedupe_key(user_id, text), source, ex=86400)
    except Exception:  # noqa: BLE001 best-effort：任何失败不得影响 run
        log.warning(
            "async preference extraction failed (best-effort)",
            extra={"source": source},
            exc_info=True,
        )


async def drain_preference_tasks() -> None:
    """等待在途抽取任务完成（测试确定性 / 优雅关停用）。"""
    while _pending:
        await asyncio.gather(*list(_pending), return_exceptions=True)


def pending_extraction_count() -> int:
    """可观测性：当前在途抽取任务数。"""
    return len(_pending)


def _reset_for_tests() -> set[asyncio.Task[None]]:
    """测试隔离：清空 pending 集合并返回旧集合（供调用方清理）。"""
    old = set(_pending)
    _pending.clear()
    return old
