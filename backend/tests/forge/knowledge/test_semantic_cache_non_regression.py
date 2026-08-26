"""Knowledge RAG 开启时 Semantic Cache 行为不退化（ADR-06 §8.3）。"""

from __future__ import annotations

import pytest
import redis.asyncio as redis

from app.core.config import settings
from app.forge.cache.pinecone_store import (
    InMemoryPineconeStore,
    reset_pinecone_store_override,
    set_pinecone_store_override,
)
from app.forge.cache.semantic import semantic_cache_lookup, semantic_cache_store
from app.forge.knowledge.retriever import retrieve_knowledge_for_node


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_pinecone_store_override()
    yield
    reset_pinecone_store_override()


@pytest.mark.asyncio
async def test_semantic_cache_unchanged_when_knowledge_rag_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "semantic_cache_direct_hit_enabled", True)

    store = InMemoryPineconeStore()
    set_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0, 0.0]

    monkeypatch.setattr("app.forge.cache.semantic.embed_one", _fake_embed)

    await semantic_cache_store(
        node="entry_router",
        query="start a platformer",
        result={"phase": "plan"},
        skill_bundle_hash="abc",
    )

    r = redis.from_url("redis://localhost:9/0", decode_responses=True)
    hit = await semantic_cache_lookup(
        r,
        node="entry_router",
        query="start a platformer",
        skill_bundle_hash="abc",
    )
    assert hit == {"phase": "plan"}

    # Knowledge path no-op without knowledge host
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "")
    chunks = await retrieve_knowledge_for_node(
        node="plan",
        current_input="platformer",
        design_doc=None,
    )
    assert chunks == []
