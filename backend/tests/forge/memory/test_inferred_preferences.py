"""Inferred / LLM 偏好路径与物理删除上限。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.forge.memory.inferred import extract_inferred_preferences
from app.forge.memory.preferences import upsert_preferences_from_text
from app.models.user import User


def test_inferred_extracts_pixel_without_explicit_marker() -> None:
    """遗留规则模块仍可单测；正式路径已切 LLM。"""
    prefs = extract_inferred_preferences("做一个像素风跑酷")
    assert len(prefs) == 1
    assert prefs[0]["source"] == "inferred"
    assert prefs[0]["value_json"]["style"] == "pixel"
    assert prefs[0]["confidence"] <= 0.5


def test_inferred_skips_when_explicit_marker_present() -> None:
    assert extract_inferred_preferences("以后都用像素风") == []


@pytest.mark.asyncio
async def test_upsert_via_llm_routes_to_service_policy(db_session, monkeypatch) -> None:
    """操作式抽取 → v2 服务：explicit 不被 inferred 覆盖、别名归一、目录外拒绝。"""
    from app.models.user_preference_v2 import UserPreferenceV2

    monkeypatch.setattr(settings, "memory_preferences", True)
    monkeypatch.setattr(settings, "memory_preferences_inferred", True)

    calls: list[list[dict]] = []

    async def fake_extract(text: str, current_prefs: list[dict], **kwargs):
        calls.append(current_prefs)
        if len(calls) == 1:
            return [
                {
                    "op": "set",
                    "key": "visual.style",
                    "value": "pixel",
                    "source": "explicit",
                    "confidence": 0.9,
                }
            ]
        return [
            {
                "op": "set",
                "key": "theme",  # 别名 → visual.style
                "value": "cartoon",
                "source": "inferred",
                "confidence": 0.4,
            },
            {
                "op": "set",
                "key": "made_up.key",  # 目录外 → 拒绝
                "value": "x",
                "source": "explicit",
                "confidence": 1.0,
            },
        ]

    monkeypatch.setattr("app.forge.memory.llm_extract.extract_preference_operations", fake_extract)
    user = User(
        id=uuid4(),
        email=f"llm-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    await upsert_preferences_from_text(db_session, user_id=user.id, text="以后都用像素风")
    # 第二次抽取应携带现有偏好摘要（合并决策输入）
    await upsert_preferences_from_text(db_session, user_id=user.id, text="这次试试卡通")
    assert calls[1] == [
        {"key": "visual.style", "value": "pixel", "source": "explicit", "confidence": 0.9}
    ]
    rows = (
        await db_session.scalars(
            select(UserPreferenceV2).where(UserPreferenceV2.user_id == user.id)
        )
    ).all()
    assert len(rows) == 1  # 别名归一同行 + 目录外拒绝
    assert rows[0].preference_key == "visual.style"
    assert rows[0].value == "pixel" and rows[0].source == "explicit"
    # 合并被拒（inferred 压不过 explicit）→ 值与溯源保持首次触发语句
    assert rows[0].note == "以后都用像素风"


@pytest.mark.asyncio
async def test_upsert_filters_inferred_when_disabled(db_session, monkeypatch) -> None:
    """memory_preferences_inferred=False：inferred 候选被丢弃，explicit 仍写入。"""
    from app.models.user_preference_v2 import UserPreferenceV2

    monkeypatch.setattr(settings, "memory_preferences", True)
    monkeypatch.setattr(settings, "memory_preferences_inferred", False)

    async def fake_extract(text: str, current_prefs: list[dict], **kwargs):
        return [
            {
                "op": "set",
                "key": "gameplay.difficulty",
                "value": "hard",
                "source": "inferred",
                "confidence": 0.6,
            },
            {
                "op": "set",
                "key": "visual.style",
                "value": "pixel",
                "source": "explicit",
                "confidence": 1.0,
            },
        ]

    monkeypatch.setattr("app.forge.memory.llm_extract.extract_preference_operations", fake_extract)
    user = User(
        id=uuid4(),
        email=f"noi-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    await upsert_preferences_from_text(db_session, user_id=user.id, text="随便说点什么")
    rows = (
        await db_session.scalars(
            select(UserPreferenceV2).where(UserPreferenceV2.user_id == user.id)
        )
    ).all()
    assert [r.preference_key for r in rows] == ["visual.style"]


@pytest.mark.asyncio
async def test_upsert_preferences_noop_without_model(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "preference_extract_model", "")
    monkeypatch.setattr(settings, "preference_extract_apikey", "")
    user = User(
        id=uuid4(),
        email=f"noop-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    written = await upsert_preferences_from_text(db_session, user_id=user.id, text="以后都用像素风")
    assert written == []


@pytest.mark.asyncio
async def test_extract_operations_parse_unit() -> None:
    from app.forge.memory.llm_extract import _parse_operations

    ops = _parse_operations(
        '{"operations":[{"op":"set","key":"visual.style","value":"pixel",'
        '"source":"explicit","confidence":0.9},'
        '{"op":"remove","key":"gameplay.genre"},'
        '{"op":"weird","key":"x"}]}'
    )
    assert [o["op"] for o in ops] == ["set", "remove"]  # 非法 op 丢弃
    assert ops[0]["key"] == "visual.style"
    fenced = _parse_operations('```json\n{"operations":[]}\n```')
    assert fenced == []
