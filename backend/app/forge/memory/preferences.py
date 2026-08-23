"""用户偏好读写（P1 Explicit；可选 Inferred）。"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_preference import UserPreference


async def list_active_preferences(db: AsyncSession, user_id: uuid.UUID) -> list[UserPreference]:
    """查询用户所有 status=active 的长期偏好。

    场景：``build_node_context`` 注入偏好；``_enforce_active_cap`` 检查上限。
    参数：db - 异步数据库会话；user_id - 用户 ID。
    返回：UserPreference ORM 行列表。
    """
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
    """按 category+key 插入或更新用户偏好。

    场景：显式/推断偏好写入；LLM 抽取结果落库。
    参数：
        db - 异步数据库会话；
        user_id - 用户 ID；
        category - 偏好类别；
        key - 偏好键；
        value_json - 偏好值 dict；
        source - 来源（explicit/inferred）；
        confidence - 置信度 0-1；
        status - 状态（默认 active）。
    返回：新建或更新后的 UserPreference 行。
    """
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
    """清空用户全部长期偏好（含 inactive）。

    场景：用户重置偏好或管理端清理。
    参数：db - 异步数据库会话；user_id - 用户 ID。
    返回：删除的行数。
    """
    rows = (await db.scalars(select(UserPreference).where(UserPreference.user_id == user_id))).all()
    count = len(rows)
    for row in rows:
        await db.delete(row)
    await db.flush()
    return count


async def upsert_preferences_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """从用户文本经 LLM 抽取偏好并写入 DB。

    场景：用户消息写入后异步提取长期偏好；正式路径禁止规则引擎。
    参数：db - 异步数据库会话；user_id - 用户 ID；text - 用户消息文本。
    返回：成功写入的 UserPreference 行列表；未配置模型或关闭功能时返回 []。
    """
    if not settings.memory_preferences:
        return []
    from app.forge.memory.llm_extract import extract_preferences_via_llm

    items = await extract_preferences_via_llm(text)
    written: list[UserPreference] = []
    for item in items:
        source = str(item.get("source") or "inferred")
        if source == "inferred" and not settings.memory_preferences_inferred:
            continue
        category = str(item["category"])
        key = str(item["key"])
        existing = await db.scalar(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.category == category,
                UserPreference.key == key,
            )
        )
        if source == "inferred" and existing is not None and existing.source == "explicit":
            continue
        row = await upsert_preference(
            db,
            user_id=user_id,
            category=category,
            key=key,
            value_json=dict(item["value_json"]),
            source=source,
            confidence=float(item.get("confidence") or 0.4),
            status=str(item.get("status") or "active"),
        )
        written.append(row)
    return written


async def upsert_explicit_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """兼容旧调用：走 LLM 正式路径（不再用规则引擎）。

    场景：历史 explicit 抽取入口转发至 ``upsert_preferences_from_text``。
    参数：db - 异步数据库会话；user_id - 用户 ID；text - 用户消息文本。
    返回：写入的 UserPreference 行列表。
    """
    return await upsert_preferences_from_text(db, user_id=user_id, text=text)


async def upsert_inferred_from_text(
    db: AsyncSession, *, user_id: uuid.UUID, text: str
) -> list[UserPreference]:
    """兼容旧调用：走 LLM 正式路径。

    场景：历史 inferred 抽取入口转发至 ``upsert_preferences_from_text``。
    参数：db - 异步数据库会话；user_id - 用户 ID；text - 用户消息文本。
    返回：写入的 UserPreference 行列表。
    """
    return await upsert_preferences_from_text(db, user_id=user_id, text=text)


def preference_to_context_dict(row: UserPreference) -> dict[str, Any]:
    """将 UserPreference ORM 行转为 ContextBuilder 可消费的 dict。

    场景：``build_node_context`` 组装 preferences section。
    参数：row - UserPreference ORM 实例。
    返回：含 category/key/value_json/source/confidence 的 dict。
    """
    return {
        "category": row.category,
        "key": row.key,
        "value_json": row.value_json,
        "source": row.source,
        "confidence": row.confidence,
    }


async def _enforce_active_cap(db: AsyncSession, user_id: uuid.UUID) -> None:
    """强制 active 偏好数量不超过配置上限。

    场景：``upsert_preference`` 写入后自动清理溢出项。
    参数：db - 异步数据库会话；user_id - 用户 ID。
    返回：无；优先删除最早 inferred，再删最早 explicit。
    """
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
