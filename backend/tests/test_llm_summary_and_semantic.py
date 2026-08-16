"""P1 LLM summary 与 P4.5 Semantic shadow。"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.core.config import settings
from app.forge.cache.semantic import (
    semantic_cache_lookup,
    semantic_direct_hit_allowed,
    semantic_shadow_record,
)
from app.forge.memory.context_builder import ContextTurn
from app.forge.memory.llm_summary import synthesize_summary_via_llm
from app.forge.memory.summary import synthesize_summary_from_turns


@pytest.mark.asyncio
async def test_llm_summary_parses_json() -> None:
    async def complete(_system: str, _user: str) -> str:
        return (
            '{"current_goal":"像素跑酷","confirmed_decisions":["双跳"],'
            '"rejected_options":[],"gameplay_constraints":[],'
            '"visual_constraints":["像素"],"technical_constraints":[],'
            '"pending_requests":[]}'
        )

    turns = [ContextTurn(role="user", content="做一个像素跑酷")]
    out = await synthesize_summary_via_llm(turns, None, complete=complete)
    assert out["current_goal"] == "像素跑酷"
    assert "双跳" in out["confirmed_decisions"]


@pytest.mark.asyncio
async def test_llm_summary_falls_back_on_bad_json() -> None:
    async def complete(_system: str, _user: str) -> str:
        return "not-json"

    turns = [ContextTurn(role="user", content="做一个像素风跑酷")]
    out = await synthesize_summary_via_llm(turns, None, complete=complete)
    expected = synthesize_summary_from_turns(turns, previous=None)
    assert out["current_goal"] == expected["current_goal"]


def test_semantic_direct_hit_always_blocked() -> None:
    assert semantic_direct_hit_allowed() is False


@pytest.mark.asyncio
async def test_semantic_lookup_never_hits() -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    assert await semantic_cache_lookup(r, node="entry_router", query={"a": 1}) is None
    assert await semantic_cache_lookup(r, node="code", query={"a": 1}) is None


@pytest.mark.asyncio
async def test_semantic_shadow_records_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(settings, "semantic_cache_shadow_enabled", True)
    ok = await semantic_shadow_record(
        r, node="entry_router", query={"q": 1}, actual_output="code", similarity=0.9
    )
    assert ok is True
    rows = await r.lrange("forge:semantic:shadow:entry_router", 0, -1)
    assert len(rows) == 1
    assert "query_hash" in rows[0]


@pytest.mark.asyncio
async def test_semantic_shadow_respects_enabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(settings, "semantic_cache_shadow_enabled", False)
    ok = await semantic_shadow_record(
        r, node="entry_router", query={"q": 1}, actual_output="code"
    )
    assert ok is False
    monkeypatch.setattr(settings, "semantic_cache_shadow_enabled", True)
    ok2 = await semantic_shadow_record(
        r, node="entry_router", query={"q": 2}, actual_output="code"
    )
    assert ok2 is True


@pytest.mark.asyncio
async def test_semantic_shadow_concurrent_trim_and_no_direct_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """并发 shadow 写入不得打开 direct hit；列表长度受 ltrim 约束。"""
    import asyncio

    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(settings, "semantic_cache_shadow_enabled", True)

    async def one(i: int) -> None:
        await semantic_shadow_record(
            r,
            node="engine_router",
            query={"i": i},
            actual_output={"v": i},
            similarity=0.1,
        )
        assert await semantic_cache_lookup(r, node="engine_router", query={"i": i}) is None

    await asyncio.gather(*(one(i) for i in range(32)))
    rows = await r.lrange("forge:semantic:shadow:engine_router", 0, -1)
    assert 1 <= len(rows) <= 1000
    assert semantic_direct_hit_allowed() is False
