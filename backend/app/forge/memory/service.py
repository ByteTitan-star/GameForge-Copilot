"""Preference Service（ADR-16）：偏好的唯一读写路径。

模型只"建议"（操作式候选），本层"裁决"：别名归一 → 目录/类型校验 → 合并策略 →
LRU 归档。resolve_for 按节点注入并刷新 last_used_at（LRU 心跳）。
归档行 agent 永不可见（所有读路径过滤 status='active'），永不物理 DELETE。
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.forge.memory.catalog import keys_for_node, slot_for, validate_candidate
from app.models.user_preference_v2 import UserPreferenceV2

log = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def _naive(dt: datetime) -> datetime:
    """排序/比较统一用 naive：sqlite 回读 naive、Postgres aware，混合比较会炸。"""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


async def list_active(db: AsyncSession, user_id: uuid.UUID) -> list[UserPreferenceV2]:
    rows = await db.scalars(
        select(UserPreferenceV2)
        .where(UserPreferenceV2.user_id == user_id, UserPreferenceV2.status == "active")
        .order_by(UserPreferenceV2.preference_key)
    )
    return list(rows.all())


async def active_digest(db: AsyncSession, user_id: uuid.UUID) -> list[dict[str, Any]]:
    """抽取合并用的现有偏好摘要（4 字段投影，不过滤节点）。"""
    return [
        {
            "key": r.preference_key,
            "value": r.value,
            "source": r.source,
            "confidence": round(float(r.confidence), 2),
        }
        for r in await list_active(db, user_id)
    ]


def _merge_allowed(
    existing: UserPreferenceV2,
    source: str,
    confidence: float,
    *,
    now: datetime | None = None,
) -> bool:
    """合并策略：explicit 恒胜；inferred 仅在置信度不低于现值时可更新。

    例外（ADR-16 增量·时间衰减复确认）：explicit 超过 preference_explicit_stale_days
    未被重新确认（updated_at 陈旧——注意不是 last_used_at，后者每次注入都会刷新，
    "被使用"不等于"被用户复确认"），且新 inferred 置信度 ≥
    preference_inferred_override_confidence 时允许覆盖——用户口味会变，
    一年前写下的 explicit 不应永远压过昨天的高置信行为信号；覆盖时旧值
    进入归档历史（note 记录），可审计可回滚。
    """
    if source == "explicit":
        return True
    if existing.source == "explicit":
        stale_days = int(settings.preference_explicit_stale_days)
        if stale_days <= 0:
            return False  # 时间衰减关闭：回到 explicit 绝对恒胜（ADR-16 原策略）
        threshold = float(settings.preference_inferred_override_confidence)
        reference = now or _now()
        updated = _naive(existing.updated_at)
        age_days = (reference.replace(tzinfo=None) - updated).days
        return age_days >= stale_days and confidence >= threshold
    return confidence >= float(existing.confidence)


async def apply_operation(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    op: dict[str, Any],
    note: str = "",
) -> UserPreferenceV2 | None:
    """应用单条操作 {op: set|remove|touch, key, value, source, confidence}。

    非法 key/value 一律返回 None（拒绝进入 active），由调用方计数观测。
    """
    kind = str(op.get("op") or "set").strip().lower()
    validated = validate_candidate(str(op.get("key") or ""), op.get("value"))
    if validated is None and kind != "remove":
        log.info("preference op rejected (unknown key/bad value): %s", op.get("key"))
        return None
    key = validated[0] if validated else str(op.get("key") or "")
    source = "explicit" if str(op.get("source") or "").strip().lower() == "explicit" else "inferred"
    try:
        confidence = max(0.0, min(1.0, float(op.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    clipped_note = (note or "").strip()[:120]

    existing = await db.scalar(
        select(UserPreferenceV2).where(
            UserPreferenceV2.user_id == user_id, UserPreferenceV2.preference_key == key
        )
    )

    if kind == "remove":
        if existing is not None and existing.status == "active":
            existing.status = "archived"
            existing.note = clipped_note or existing.note
            existing.updated_at = _now()
            await db.flush()
        return existing

    if kind == "touch":
        if existing is not None and existing.status == "active":
            existing.last_used_at = _now()
            await db.flush()
        return existing

    # set：validated 非空且 remove 已提前返回，此处必为有效候选
    assert validated is not None
    value = validated[1]
    slot = slot_for(key)
    value_type = slot.type if slot is not None else "enum"
    if existing is None:
        row = UserPreferenceV2(
            user_id=user_id,
            preference_key=key,
            value=value,
            value_type=value_type,
            source=source,
            confidence=confidence,
            status="active",
            note=clipped_note,
        )
        db.add(row)
        await db.flush()
        await _enforce_cap(db, user_id)
        return row

    if existing.status != "active":
        # 归档行复活：按新操作整体重建
        existing.status = "active"
        existing.value = value
        existing.source = source
        existing.confidence = confidence
        existing.note = clipped_note
        existing.last_used_at = _now()
        existing.updated_at = _now()
        await db.flush()
        await _enforce_cap(db, user_id)
        return existing

    if not _merge_allowed(existing, source, confidence):
        # inferred 压不过现值：仅刷新 LRU 心跳，值保持
        existing.last_used_at = _now()
        await db.flush()
        return existing

    # 陈旧 explicit 被高置信 inferred 覆盖：note 留痕可审计回滚
    supersede_mark = ""
    if existing.source == "explicit" and source == "inferred":
        supersede_mark = f" | superseded_explicit:{existing.value}"
    existing.value = value
    existing.source = source
    existing.confidence = confidence
    existing.note = (clipped_note or existing.note) + supersede_mark
    existing.last_used_at = _now()
    existing.updated_at = _now()
    await db.flush()
    await _enforce_cap(db, user_id)
    return existing


async def apply_operations(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    ops: list[dict[str, Any]],
    note: str = "",
) -> list[UserPreferenceV2]:
    """整批应用：同 key 后 op 覆盖前 op（单消息防抖：一次抽取里最后说了算）。"""
    by_key: dict[str, dict[str, Any]] = {}
    for op in ops:
        validated = validate_candidate(str(op.get("key") or ""), op.get("value"))
        key = validated[0] if validated else str(op.get("key") or "")
        if key:
            by_key[key] = op
    written: list[UserPreferenceV2] = []
    for op in by_key.values():
        row = await apply_operation(db, user_id=user_id, op=op, note=note)
        if row is not None:
            written.append(row)
    return written


async def resolve_for(
    db: AsyncSession, user_id: uuid.UUID, node: str
) -> list[UserPreferenceV2]:
    """节点可见的活跃偏好（4 字段投影由调用方做）+ 批量 touch（LRU 心跳）。"""
    keys = keys_for_node(node)
    if not keys:
        return []
    rows = await db.scalars(
        select(UserPreferenceV2).where(
            UserPreferenceV2.user_id == user_id,
            UserPreferenceV2.status == "active",
            UserPreferenceV2.preference_key.in_(keys),
        )
    )
    hits = list(rows.all())
    if hits:
        await db.execute(
            update(UserPreferenceV2)
            .where(
                UserPreferenceV2.user_id == user_id,
                UserPreferenceV2.status == "active",
                UserPreferenceV2.preference_key.in_([r.preference_key for r in hits]),
            )
            .values(last_used_at=_now())
        )
    return hits


async def clear_all(db: AsyncSession, user_id: uuid.UUID) -> int:
    """清空（用户显式动作）：归档而非删除；返回归档行数。"""
    rows = (
        await db.scalars(
            select(UserPreferenceV2).where(
                UserPreferenceV2.user_id == user_id, UserPreferenceV2.status == "active"
            )
        )
    ).all()
    for row in rows:
        row.status = "archived"
        row.updated_at = _now()
    await db.flush()
    return len(rows)


async def _enforce_cap(db: AsyncSession, user_id: uuid.UUID) -> None:
    """活跃上限：按 last_used_at 最旧归档（explicit 不豁免）；永不物理删除。"""
    cap = max(1, int(settings.memory_preferences_max_active))
    active = await list_active(db, user_id)
    overflow = len(active) - cap
    if overflow <= 0:
        return
    ordered = sorted(active, key=lambda r: _naive(r.last_used_at))
    for row in ordered[:overflow]:
        row.status = "archived"
        row.note = (row.note or "") + " | archived_by_cap"
    await db.flush()
