"""偏好抽取异步化（ADR-18 follow-up）：调度 / 去重 / 失败不扩散 / 确定性 drain。"""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import pytest

from app.forge.memory import async_extract


@pytest.fixture(autouse=True)
def _isolate_pending() -> None:
    async_extract._reset_for_tests()


async def test_schedule_runs_extraction_in_background(
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """调度后任务在后台执行 upsert_preferences_from_text（新 session 提交）。"""
    calls: list[str] = []

    async def _fake_upsert(s, *, user_id, text, history_texts=None):
        calls.append(text)

    captured_sessions: list[object] = []

    class _FakeSession:
        async def __aenter__(self):
            captured_sessions.append(self)
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            return None

        async def scalars(self, *_a, **_k):
            class _Empty:
                def all(self):
                    return []
            return _Empty()

    from app.core import db as dbmod

    monkeypatch.setattr(
        "app.forge.memory.preferences.upsert_preferences_from_text", _fake_upsert
    )
    monkeypatch.setattr(dbmod, "SessionLocal", lambda: _FakeSession())

    async_extract.schedule_preference_extraction(redis_client, uuid.uuid4(), "以后都做像素风")
    assert async_extract.pending_extraction_count() == 1
    await async_extract.drain_preference_tasks()

    assert calls == ["以后都做像素风"]
    assert async_extract.pending_extraction_count() == 0


async def test_schedule_dedupes_same_text(
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 (user, text) 第二次调度被去重键拦下，不重复抽取。"""
    calls: list[str] = []

    async def _fake_upsert(s, *, user_id, text, history_texts=None):
        calls.append(text)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            return None

        async def scalars(self, *_a, **_k):
            class _Empty:
                def all(self):
                    return []
            return _Empty()

    from app.core import db as dbmod

    monkeypatch.setattr(
        "app.forge.memory.preferences.upsert_preferences_from_text", _fake_upsert
    )
    monkeypatch.setattr(dbmod, "SessionLocal", lambda: _FakeSession())

    user = uuid.uuid4()
    async_extract.schedule_preference_extraction(redis_client, user, "固定文本")
    await async_extract.drain_preference_tasks()
    async_extract.schedule_preference_extraction(redis_client, user, "固定文本")
    await async_extract.drain_preference_tasks()

    assert calls == ["固定文本"]  # 第二次被 24h 去重键拦截


async def test_schedule_failure_is_swallowed(
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """抽取抛错只 log 不扩散（best-effort），drain 正常返回。"""

    async def _boom(s, *, user_id, text):
        raise RuntimeError("extract llm down")

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def commit(self):
            return None

        async def scalars(self, *_a, **_k):
            class _Empty:
                def all(self):
                    return []
            return _Empty()

    from app.core import db as dbmod

    monkeypatch.setattr(
        "app.forge.memory.preferences.upsert_preferences_from_text", _boom
    )
    monkeypatch.setattr(dbmod, "SessionLocal", lambda: _FakeSession())

    async_extract.schedule_preference_extraction(redis_client, uuid.uuid4(), "文本")
    await async_extract.drain_preference_tasks()  # 不 raise
    # 失败不写去重键：下次同文本仍可重试
    assert await redis_client.keys("pref:extract:dedupe:*") == []


async def test_schedule_skips_when_disabled(
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """memory_preferences 关闭或空文本：不创建任务。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "memory_preferences", False)
    async_extract.schedule_preference_extraction(redis_client, uuid.uuid4(), "文本")
    async_extract.schedule_preference_extraction(redis_client, uuid.uuid4(), "   ")
    assert async_extract.pending_extraction_count() == 0
