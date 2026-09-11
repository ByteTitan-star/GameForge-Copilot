"""Preference Service（ADR-16）：策略裁决 / LRU 归档 / 按节点解析。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.forge.memory import service as svc
from app.forge.memory.service import _naive
from app.models.user_preference_v2 import UserPreferenceV2

_U = uuid.uuid4


async def ap(db: AsyncSession, uid: uuid.UUID, op: dict, note: str = ""):
    """svc.apply_operation 的短封装，压测试行宽。"""
    return await svc.apply_operation(db, user_id=uid, op=op, note=note)


def _set(key: str, value: str, source: str = "explicit", confidence: float = 1.0) -> dict:
    return {"op": "set", "key": key, "value": value, "source": source, "confidence": confidence}


def _inf(key: str, value: str, confidence: float) -> dict:
    """inferred 短构型，压行宽。"""
    return _set(key, value, source="inferred", confidence=confidence)


async def test_same_intent_different_alias_one_row(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _set("visual.style", "pixel"), note="我喜欢像素风")
    await ap(db_session, uid, _inf("theme", "neon", 0.9))
    rows = await svc.list_active(db_session, uid)
    assert [r.preference_key for r in rows] == ["visual.style"]
    # inferred(0.9) 覆盖 explicit → 被合并策略拒绝，值保持 pixel
    assert rows[0].value == "pixel" and rows[0].source == "explicit"


async def test_unknown_key_and_bad_value_rejected(db_session: AsyncSession) -> None:
    uid = _U()
    assert await ap(db_session, uid, _set("random.schema_key", "x")) is None
    assert await ap(db_session, uid, _set("visual.style", "watercolor")) is None
    assert await svc.list_active(db_session, uid) == []


async def test_inferred_upgrade_when_higher_confidence(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _inf("gameplay.difficulty", "normal", 0.6))
    row = await ap(db_session, uid, _inf("gameplay.difficulty", "hard", 0.8))
    assert row is not None and row.value == "hard"  # 同级 inferred 置信度更高 → 允许更新
    row = await ap(db_session, uid, _inf("gameplay.difficulty", "easy", 0.7))
    assert row is not None and row.value == "hard"  # 更低置信度 → 仅 touch


async def test_remove_archives_and_resolver_invisible(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _set("visual.palette", "dark"))
    row = await ap(db_session, uid, {"op": "remove", "key": "visual.palette"}, note="别再默认暗色")
    assert row is not None and row.status == "archived"
    assert await svc.list_active(db_session, uid) == []
    assert await svc.resolve_for(db_session, uid, "art") == []


async def test_archived_row_resurrects_on_new_set(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _inf("gameplay.genre", "racing", 0.7))
    await ap(db_session, uid, {"op": "remove", "key": "gameplay.genre"})
    row = await ap(db_session, uid, _set("gameplay.genre", "roguelike"))
    assert row is not None and row.status == "active" and row.value == "roguelike"


async def test_resolve_for_scopes_and_touches(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _inf("gameplay.difficulty", "hard", 0.65))
    await ap(db_session, uid, _set("visual.palette", "dark"))
    old = datetime.now() - timedelta(days=30)  # naive：与 sqlite 返回值一致
    row = (await svc.list_active(db_session, uid))[0]
    row.last_used_at = old
    await db_session.flush()

    art_rows = await svc.resolve_for(db_session, uid, "art")
    assert [r.preference_key for r in art_rows] == ["visual.palette"]  # difficulty 不属于 art

    plan_rows = await svc.resolve_for(db_session, uid, "plan")
    assert {r.preference_key for r in plan_rows} == {"gameplay.difficulty"}  # palette 不属于 plan
    # touch：30 天前的 last_used_at 被刷新到近期
    after = (await svc.list_active(db_session, uid))[0]
    assert _naive(after.last_used_at) > old + timedelta(days=29)


async def test_cap_lru_archive_never_delete(db_session: AsyncSession, monkeypatch) -> None:
    uid = _U()
    monkeypatch.setattr(settings, "memory_preferences_max_active", 3)
    base = datetime.now() - timedelta(days=10)  # naive：与 sqlite 返回值一致
    for i, key in enumerate(("visual.style", "visual.palette", "visual.mood")):
        row = await ap(db_session, uid, _set(key, ("pixel", "dark", "calm")[i]))
        assert row is not None
        row.last_used_at = base + timedelta(days=i)
    await db_session.flush()
    by_key = {r.preference_key: r for r in await svc.list_active(db_session, uid)}
    stale_id = by_key["visual.style"].id  # last_used_at 最早（base+0）

    await ap(db_session, uid, _set("ui.language", "zh"))  # 触发 4>3

    active = await svc.list_active(db_session, uid)
    assert len(active) == 3 and all(r.id != stale_id for r in active)
    archived = (
        await db_session.scalars(
            select(UserPreferenceV2).where(
                UserPreferenceV2.user_id == uid, UserPreferenceV2.status == "archived"
            )
        )
    ).all()
    assert len(archived) == 1 and archived[0].id == stale_id  # 归档而非删除
    assert "archived_by_cap" in archived[0].note


async def test_batch_last_op_wins(db_session: AsyncSession) -> None:
    uid = _U()
    written = await svc.apply_operations(
        db_session,
        user_id=uid,
        ops=[
            _set("gameplay.difficulty", "easy"),
            _set("gameplay.difficulty", "hard"),  # 同消息后说覆盖前说
            _set("visual.style", "pixel"),
        ],
        note="一次抽取",
    )
    values = {r.preference_key: r.value for r in written}
    assert values == {"gameplay.difficulty": "hard", "visual.style": "pixel"}


async def test_clear_all_archives(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _set("visual.style", "pixel"))
    count = await svc.clear_all(db_session, uid)
    assert count == 1 and await svc.list_active(db_session, uid) == []


@pytest.mark.parametrize("node", ["code", "repair", "qa"])
async def test_code_family_nodes_get_nothing(db_session: AsyncSession, node: str) -> None:
    uid = _U()
    await ap(db_session, uid, _set("visual.style", "pixel"))
    assert await svc.resolve_for(db_session, uid, node) == []


async def test_digest_projection(db_session: AsyncSession) -> None:
    uid = _U()
    await ap(db_session, uid, _set("visual.style", "pixel"))
    digest = await svc.active_digest(db_session, uid)
    assert digest == [
        {"key": "visual.style", "value": "pixel", "source": "explicit", "confidence": 1.0}
    ]
