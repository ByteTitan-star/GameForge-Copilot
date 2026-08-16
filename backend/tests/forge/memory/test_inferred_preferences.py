"""Inferred / LLM 偏好路径与物理删除上限。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.forge.memory.inferred import extract_inferred_preferences
from app.forge.memory.llm_extract import extract_preferences_via_llm
from app.forge.memory.preferences import (
    list_active_preferences,
    upsert_preference,
    upsert_preferences_from_text,
)
from app.models.user import User
from app.models.user_preference import UserPreference


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
async def test_upsert_via_llm_does_not_overwrite_explicit(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_preferences", True)
    monkeypatch.setattr(settings, "memory_preferences_inferred", True)

    calls = {"n": 0}

    async def fake_extract(text: str):
        calls["n"] += 1
        if calls["n"] == 1:
            return [
                {
                    "category": "visual",
                    "key": "style",
                    "value_json": {"style": "pixel"},
                    "source": "explicit",
                    "confidence": 0.9,
                }
            ]
        return [
            {
                "category": "visual",
                "key": "style",
                "value_json": {"style": "cartoon"},
                "source": "inferred",
                "confidence": 0.4,
            }
        ]

    monkeypatch.setattr("app.forge.memory.llm_extract.extract_preferences_via_llm", fake_extract)
    user = User(
        id=uuid4(),
        email=f"llm-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    await upsert_preferences_from_text(db_session, user_id=user.id, text="以后都用像素风")
    await upsert_preferences_from_text(db_session, user_id=user.id, text="这次改成卡通风格试试")
    row = await db_session.scalar(
        select(UserPreference).where(
            UserPreference.user_id == user.id,
            UserPreference.category == "visual",
            UserPreference.key == "style",
        )
    )
    assert row is not None
    assert row.source == "explicit"
    assert row.value_json.get("style") == "pixel"


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
async def test_llm_extract_parser_unit(monkeypatch) -> None:
    monkeypatch.setattr(settings, "preference_extract_enabled", True)
    monkeypatch.setattr(settings, "preference_extract_model", "tiny")
    monkeypatch.setattr(settings, "preference_extract_apikey", "sk-test")
    monkeypatch.setattr(settings, "preference_extract_provider", "openai_compat")
    monkeypatch.setattr(settings, "preference_extract_base_url", "http://localhost:9")

    async def fake_complete(*_a, **_k):
        return (
            '{"preferences":[{"category":"visual","key":"style",'
            '"value_json":{"style":"pixel"},"source":"explicit","confidence":0.9}]}',
            None,
        )

    monkeypatch.setattr("app.llm.provider.complete", fake_complete)
    rows = await extract_preferences_via_llm("以后都用像素风")
    assert len(rows) == 1
    assert rows[0]["source"] == "explicit"


@pytest.mark.asyncio
async def test_active_preferences_physically_deleted_over_cap(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_preferences_max_active", 50)
    user = User(
        id=uuid4(),
        email=f"cap-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    for i in range(55):
        await upsert_preference(
            db_session,
            user_id=user.id,
            category="misc",
            key=f"k{i}",
            value_json={"n": i},
            source="inferred",
        )
    active = await list_active_preferences(db_session, user.id)
    assert len(active) == 50
    total = await db_session.scalar(
        select(func.count()).select_from(UserPreference).where(UserPreference.user_id == user.id)
    )
    assert total == 50
