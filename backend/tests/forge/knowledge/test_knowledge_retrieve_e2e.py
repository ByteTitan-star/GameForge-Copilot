"""Ingest → retrieve roundtrip (in-memory Pinecone)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.ingest import KnowledgeChunkSpec, upsert_knowledge_spec
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.retriever import retrieve_knowledge_for_node


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


@pytest.mark.asyncio
async def test_ingest_then_retrieve_for_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)

    spec = KnowledgeChunkSpec(
        chunk_id="design-mechanic-test",
        text="肉鸽塔防 随机成长 协同 build synergy 机制设计",
        domain="design",
        category="gameplay_mechanic",
        title="Roguelike Tower Defense",
        source_id="test-src",
        acl="internal",
    )
    assert await upsert_knowledge_spec(spec) is True

    hits = await retrieve_knowledge_for_node(
        node="plan",
        current_input="帮我设计一个肉鸽塔防游戏",
        design_doc={"title": "随机塔防", "genre": "roguelike"},
    )
    assert len(hits) >= 1
    assert hits[0].domain == "design"
    assert "肉鸽" in hits[0].text or "塔防" in hits[0].text
