"""Inferred 偏好：弱信号抽取且不覆盖 Explicit。"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.forge.memory.inferred import extract_inferred_preferences
from app.forge.memory.preferences import (
    upsert_explicit_from_text,
    upsert_inferred_from_text,
)
from app.models.user import User
from app.models.user_preference import UserPreference


def test_inferred_extracts_pixel_without_explicit_marker() -> None:
    prefs = extract_inferred_preferences("做一个像素风跑酷")
    assert len(prefs) == 1
    assert prefs[0]["source"] == "inferred"
    assert prefs[0]["value_json"]["style"] == "pixel"
    assert prefs[0]["confidence"] <= 0.5


def test_inferred_skips_when_explicit_marker_present() -> None:
    assert extract_inferred_preferences("以后都用像素风") == []


@pytest.mark.asyncio
async def test_inferred_does_not_overwrite_explicit(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_preferences_inferred", True)
    user = User(
        id=uuid4(),
        email=f"inf-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    await upsert_explicit_from_text(db_session, user_id=user.id, text="以后都用像素风")
    await upsert_inferred_from_text(
        db_session, user_id=user.id, text="这次改成卡通风格试试"
    )
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
async def test_inferred_writes_when_empty(db_session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_preferences_inferred", True)
    user = User(
        id=uuid4(),
        email=f"inf2-{uuid4().hex[:8]}@example.com",
        password_hash="x",
        email_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    written = await upsert_inferred_from_text(
        db_session, user_id=user.id, text="做一个硬核平台跳跃"
    )
    assert written
    assert written[0].source == "inferred"
    assert written[0].value_json.get("difficulty") == "hard"
