"""一次性迁移（ADR-16）：旧开放键 → 目录键（命中 active / 未命中 archived）。"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.user_preference import UserPreference
from app.models.user_preference_v2 import UserPreferenceV2
from scripts.migrate_preferences_v2 import migrate


async def _seed_old(
    db: AsyncSession, uid: uuid.UUID, category: str, key: str, value_json: dict
) -> None:
    db.add(
        UserPreference(
            user_id=uid,
            category=category,
            key=key,
            value_json=value_json,
            source="explicit",
            confidence=0.9,
        )
    )


async def test_migration_maps_and_archives(db_session: AsyncSession) -> None:
    uid = uuid.uuid4()
    user = User(
        id=uid,
        email=f"mig-{uid.hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await _seed_old(db_session, uid, "visual", "style", {"style": "pixel"})  # 命中
    await _seed_old(db_session, uid, "theme", "aesthetic", {"theme": "neon"})  # 别名命中
    await _seed_old(db_session, uid, "monetization", "model", {"model": "ads"})  # 目录外
    await db_session.commit()

    stats = await migrate(apply=False)  # dry-run 不落库
    v2_rows = (
        await db_session.scalars(select(UserPreferenceV2).where(UserPreferenceV2.user_id == uid))
    ).all()
    assert len(v2_rows) == 0
    # 两类旧键归一到同一槽位 → 迁移内即坍缩为一行（skipped_existing 接住第二行）
    assert stats["migrated_active"] == 1 and stats["unmapped_archived"] == 1

    stats = await migrate(apply=True)
    rows = {
        r.preference_key: r
        for r in (
            await db_session.scalars(
                select(UserPreferenceV2).where(UserPreferenceV2.user_id == uid)
            )
        ).all()
    }
    # 两类旧键归一到同一目录槽位 → 一行
    style = rows["visual.style"]
    assert style.value in ("pixel", "neon") and style.status == "active"
    assert style.note.startswith("migrated from")
    # 目录外 → archived，仅审计可见
    unmapped = [r for r in rows.values() if r.status == "archived"]
    assert len(unmapped) == 1
    assert "unmapped" in unmapped[0].note

    # 重跑：全部跳过（幂等）
    stats2 = await migrate(apply=True)
    assert stats2["skipped_existing"] == 3
