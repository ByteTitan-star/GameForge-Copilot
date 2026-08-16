"""P1 LLM summary 与 ADR-06 Semantic 分层命中。"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import (
    InMemoryPineconeStore,
    reset_pinecone_store_override,
    set_pinecone_store_override,
)
from app.forge.cache.semantic import (
    semantic_cache_lookup,
    semantic_cache_store,
    semantic_direct_hit_allowed,
    semantic_shadow_record,
)
from app.forge.memory.context_builder import ContextTurn
from app.forge.memory.llm_summary import synthesize_summary_via_llm
from app.forge.memory.summary import synthesize_summary_from_turns


@pytest.fixture
def memory_pinecone(monkeypatch: pytest.MonkeyPatch):
    store = InMemoryPineconeStore()
    set_pinecone_store_override(store)
    monkeypatch.setattr(settings, "semantic_cache_direct_hit_enabled", True)
    monkeypatch.setattr(settings, "semantic_cache_soft_threshold", 0.85)
    monkeypatch.setattr(settings, "semantic_cache_hard_threshold", 0.95)

    async def fake_embed(text: str):
        # 稳定伪向量：字符 ordinal 归一化
        vals = [((ord(c) % 97) / 97.0) for c in (text or "x")[:32]]
        while len(vals) < 8:
            vals.append(0.1)
        return vals[:8]

    monkeypatch.setattr("app.forge.cache.semantic.embed_one", fake_embed)
    yield store
    reset_pinecone_store_override()


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


def test_semantic_direct_hit_follows_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "semantic_cache_direct_hit_enabled", True)
    assert semantic_direct_hit_allowed() is True
    monkeypatch.setattr(settings, "semantic_cache_direct_hit_enabled", False)
    assert semantic_direct_hit_allowed() is False


@pytest.mark.asyncio
async def test_semantic_lookup_miss_below_soft(
    memory_pinecone, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = memory_pinecone
    await semantic_cache_store(
        node="entry_router",
        query={"requirement": "做个射击游戏", "has_prior_version": False},
        result="greenfield",
        skill_bundle_hash="h1",
    )

    async def fake_query(*, values, top_k=1, filter=None):
        matches = await InMemoryPineconeStore.query(
            store, values=values, top_k=top_k, filter=filter
        )
        if not matches:
            return []
        from app.forge.cache.pinecone_store import VectorMatch

        m = matches[0]
        return [VectorMatch(id=m.id, score=0.84, metadata=m.metadata)]

    monkeypatch.setattr(store, "query", fake_query)
    hit = await semantic_cache_lookup(
        r,
        node="entry_router",
        query={"requirement": "zzz", "has_prior_version": True},
        skill_bundle_hash="h1",
    )
    assert hit is None


@pytest.mark.asyncio
async def test_semantic_hard_hit_returns_cached(memory_pinecone) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    payload = {"requirement": "做一个像素跑酷", "has_prior_version": False}
    await semantic_cache_store(
        node="entry_router",
        query=payload,
        result="greenfield",
        skill_bundle_hash="h1",
    )
    hit = await semantic_cache_lookup(
        r, node="entry_router", query=payload, skill_bundle_hash="h1"
    )
    assert hit == "greenfield"


@pytest.mark.asyncio
async def test_semantic_soft_hit_uses_confirm_llm(
    memory_pinecone, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = memory_pinecone
    base = {"requirement": "做一个像素跑酷游戏", "has_prior_version": False}
    await semantic_cache_store(
        node="entry_router",
        query=base,
        result="greenfield",
        skill_bundle_hash="h1",
    )

    async def fake_query(*, values, top_k=1, filter=None):
        matches = await InMemoryPineconeStore.query(
            store, values=values, top_k=top_k, filter=filter
        )
        if not matches:
            return []
        # 强制落在 soft 带
        from app.forge.cache.pinecone_store import VectorMatch

        m = matches[0]
        return [VectorMatch(id=m.id, score=0.90, metadata=m.metadata)]

    monkeypatch.setattr(store, "query", fake_query)
    monkeypatch.setattr(settings, "semantic_confirm_model", "tiny")
    monkeypatch.setattr(settings, "semantic_confirm_apikey", "sk-test")
    monkeypatch.setattr(settings, "semantic_confirm_base_url", "http://localhost:9")
    monkeypatch.setattr(settings, "semantic_confirm_provider", "openai_compat")

    async def fake_complete(*_a, **_k):
        return ('{"ok":true,"result":"greenfield"}', None)

    monkeypatch.setattr("app.llm.provider.complete", fake_complete)

    near = {"requirement": "做一个像素跑酷", "has_prior_version": False}
    hit = await semantic_cache_lookup(
        r, node="entry_router", query=near, skill_bundle_hash="h1"
    )
    assert hit == "greenfield"


@pytest.mark.asyncio
async def test_semantic_lookup_skips_forbidden_node(memory_pinecone) -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
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
