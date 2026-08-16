"""用户偏好读写（P1 Explicit；可选 Inferred）。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
        return row
    existing.value_json = value_json
    existing.source = source
    existing.confidence = confidence
    existing.status = status
    await db.flush()
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


async def upsert_explicit_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    from app.forge.memory.explicit import extract_explicit_preferences

    written: list[UserPreference] = []
    for item in extract_explicit_preferences(text):
        row = await upsert_preference(
            db,
            user_id=user_id,
            category=str(item["category"]),
            key=str(item["key"]),
            value_json=dict(item["value_json"]),
            source=str(item.get("source") or "explicit"),
            confidence=float(item.get("confidence") or 0.8),
            status=str(item.get("status") or "active"),
        )
        written.append(row)
    return written


async def upsert_inferred_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """写入 Inferred；若同 category/key 已是 Explicit 则跳过，避免降级覆盖。"""
    from app.forge.memory.inferred import extract_inferred_preferences

    written: list[UserPreference] = []
    for item in extract_inferred_preferences(text):
        category = str(item["category"])
        key = str(item["key"])
        existing = await db.scalar(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.category == category,
                UserPreference.key == key,
            )
        )
        if existing is not None and existing.source == "explicit":
            continue
        row = await upsert_preference(
            db,
            user_id=user_id,
            category=category,
            key=key,
            value_json=dict(item["value_json"]),
            source="inferred",
            confidence=float(item.get("confidence") or 0.4),
            status=str(item.get("status") or "active"),
        )
        written.append(row)
    return written


def preference_to_context_dict(row: UserPreference) -> dict[str, Any]:
    return {
        "category": row.category,
        "key": row.key,
        "value_json": row.value_json,
        "source": row.source,
        "confidence": row.confidence,
    }
