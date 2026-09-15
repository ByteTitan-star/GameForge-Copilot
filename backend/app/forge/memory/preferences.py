"""用户偏好读写（P1 Explicit；可选 Inferred）。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_preference import UserPreference


async def list_active_preferences(
    db: AsyncSession, user_id: uuid.UUID
) -> list[UserPreference]:
    rows = await db.scalars(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.status == "active",
        )
    )
    return list(rows.all())


async def upsert_preference(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: str,
    key: str,
    value_json: dict[str, Any],
    source: str = "explicit",
    confidence: float = 1.0,
    status: str = "active",
) -> UserPreference:
    existing = await db.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
            UserPreference.key == key,
        )
    )
    if existing is None:
        row = UserPreference(
            user_id=user_id,
            category=category,
            key=key,
            value_json=value_json,
            source=source,
            confidence=confidence,
            status=status,
        )
        db.add(row)
        await db.flush()
        await _enforce_active_cap(db, user_id)
        return row
    existing.value_json = value_json
    existing.source = source
    existing.confidence = confidence
    existing.status = status
    await db.flush()
    await _enforce_active_cap(db, user_id)
    return existing


async def clear_preferences(db: AsyncSession, user_id: uuid.UUID) -> int:
    """清空用户全部长期偏好（含 inactive）；返回删除行数。"""
    rows = (
        await db.scalars(select(UserPreference).where(UserPreference.user_id == user_id))
    ).all()
    count = len(rows)
    for row in rows:
        await db.delete(row)
    await db.flush()
    return count


async def upsert_preferences_from_text(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    text: str,
    history_texts: list[str] | None = None,
) -> list[Any]:
    """正式写路径（ADR-16）：操作式抽取 → Preference Service 裁决入库。

    返回实际写入/更新的 v2 行；抽取失败或未配置模型返回 []。
    合并策略（explicit 恒胜 / 置信度门槛 / 陈旧 explicit 时间衰减）与
    LRU 归档在服务层实现。history_texts 供行为信号推断（反复出现的口味模式）。
    """
    if not settings.memory_preferences:
        return []
    from app.forge.memory import service
    from app.forge.memory.llm_extract import extract_preference_operations

    digest = await service.active_digest(db, user_id)
    ops = await extract_preference_operations(text, digest, history_texts=history_texts)
    if not settings.memory_preferences_inferred:
        ops = [op for op in ops if op.get("source") != "inferred"]
    return await service.apply_operations(
        db, user_id=user_id, ops=ops, note=(text or "").strip()[:120]
    )


async def upsert_explicit_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """兼容旧调用：走 LLM 正式路径（不再用规则引擎）。"""
    return await upsert_preferences_from_text(db, user_id=user_id, text=text)


async def upsert_inferred_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """兼容旧调用：走 LLM 正式路径。"""
    return await upsert_preferences_from_text(db, user_id=user_id, text=text)


def preference_to_context_dict(row: UserPreference) -> dict[str, Any]:
    return {
        "category": row.category,
        "key": row.key,
        "value_json": row.value_json,
        "source": row.source,
        "confidence": row.confidence,
    }


async def _enforce_active_cap(db: AsyncSession, user_id: uuid.UUID) -> None:
    """active 偏好上限：物理删除最早 inferred，再删最早 explicit。"""
    cap = max(1, int(settings.memory_preferences_max_active))
    active = await list_active_preferences(db, user_id)
    overflow = len(active) - cap
    if overflow <= 0:
        return
    ordered = sorted(
        active,
        key=lambda r: (
            0 if r.source == "inferred" else 1,
            r.updated_at or r.created_at,
        ),
    )
    for row in ordered[:overflow]:
        await db.delete(row)
    await db.flush()
