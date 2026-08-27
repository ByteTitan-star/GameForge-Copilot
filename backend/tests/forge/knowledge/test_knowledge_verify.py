"""Knowledge post-ingest verify tests."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.ingest import KnowledgeChunkSpec, upsert_knowledge_spec
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.verify import verify_knowledge_retrieval


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


@pytest.mark.asyncio
async def test_verify_knowledge_retrieval_after_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", False)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", False)

    spec = KnowledgeChunkSpec(
        chunk_id="verify-chunk",
        text="肉鸽塔防 随机成长 协同机制",
        domain="design",
        category="gameplay_mechanic",
        title="验证块",
        source_id="test",
    )
    assert await upsert_knowledge_spec(spec) is True

    ok, detail = await verify_knowledge_retrieval([spec])
    assert ok is True
    assert "hits=" in detail


@pytest.mark.asyncio
async def test_ingest_fails_fast_without_pinecone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.forge.knowledge.ingest import ingest_corpus

    monkeypatch.setattr(settings, "pinecone_knowledge_host", "")

    spec = KnowledgeChunkSpec(
        chunk_id="x",
        text="t",
        domain="design",
        category="c",
        title="t",
        source_id="s",
    )
    result = await ingest_corpus([spec], dry_run=False)
    assert result.upserted == 0
    assert result.errors
    assert "PINECONE_KNOWLEDGE_HOST" in result.errors[0]
