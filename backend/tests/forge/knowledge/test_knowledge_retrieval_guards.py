"""Knowledge retrieval guards (#147 P0)."""

from __future__ import annotations

import asyncio

import pytest

from app.core.config import settings
from app.core.metrics import KNOWLEDGE_RETRIEVE_TOTAL
from app.forge.cache.pinecone_store import InMemoryPineconeStore, VectorMatch
from app.forge.knowledge.guards import (
    clip_query_text,
    effective_relevance_score,
    filter_by_min_relevance,
    validate_embedding_dim,
)
from app.forge.knowledge.ingest import KnowledgeChunkSpec, upsert_knowledge_spec
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.query_builder import build_retrieval_query
from app.forge.knowledge.retriever import retrieve_knowledge_for_node
from app.forge.knowledge.types import RetrievedKnowledge


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


def _chunk(score: float) -> RetrievedKnowledge:
    return RetrievedKnowledge(
        chunk_id="c1",
        domain="design",
        category="gameplay_mechanic",
        title="t",
        text="body",
        retrieval_score=score,
        source_id="s",
        rerank_score=score,
    )


def test_clip_query_text_respects_token_cap() -> None:
    long_text = "塔防" * 500
    clipped = clip_query_text(long_text, max_tokens=10)
    assert clipped.endswith("…")
    assert len(clipped) < len(long_text)


def test_filter_by_min_relevance_abstains_low_scores() -> None:
    chunks = [_chunk(0.9), _chunk(0.2)]
    out = filter_by_min_relevance(chunks, min_score=0.35)
    assert len(out) == 1
    assert effective_relevance_score(out[0]) >= 0.35


def test_validate_embedding_dim(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 512)
    assert validate_embedding_dim([0.0] * 512) is True
    assert validate_embedding_dim([0.0] * 128) is False
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 0)
    assert validate_embedding_dim([0.0] * 128) is True


def test_query_builder_clips_to_configured_max_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_query_max_tokens", 8)
    q = build_retrieval_query(
        node="plan",
        current_input="塔防" * 200,
        design_doc={"title": "随机塔防"},
    )
    assert q is not None
    assert q.query_text.endswith("…")


@pytest.mark.asyncio
async def test_retrieve_no_hit_when_all_below_relevance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0, 0.5]

    async def _low_score_query(*_args: object, **_kwargs: object) -> list[VectorMatch]:
        return [
            VectorMatch(
                id="low",
                score=0.1,
                metadata={
                    "text": "弱相关",
                    "domain": "design",
                    "category": "gameplay_mechanic",
                    "title": "low",
                    "source_id": "s",
                    "acl": "internal",
                },
            )
        ]

    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)
    monkeypatch.setattr(store, "query", _low_score_query)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_min_relevance_score", 0.35)
    monkeypatch.setattr(settings, "knowledge_semantic_rerank_enabled", False)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 3)

    before = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "no_hit")._value.get()  # noqa: SLF001
    hits = await retrieve_knowledge_for_node(
        node="plan",
        current_input="做一个塔防游戏",
    )
    after = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "no_hit")._value.get()  # noqa: SLF001

    assert hits == []
    assert after == before + 1


@pytest.mark.asyncio
async def test_retrieve_fail_on_embedding_dim_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _wrong_dim(_text: str) -> list[float]:
        return [1.0, 0.0]

    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _wrong_dim)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 512)

    before = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "fail")._value.get()  # noqa: SLF001
    hits = await retrieve_knowledge_for_node(
        node="plan",
        current_input="做一个塔防游戏",
    )
    after = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "fail")._value.get()  # noqa: SLF001

    assert hits == []
    assert after == before + 1


@pytest.mark.asyncio
async def test_retrieve_timeout_records_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _slow_embed(_text: str) -> list[float]:
        await asyncio.sleep(0.2)
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _slow_embed)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_retrieve_timeout_s", 0.05)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 3)

    before = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "timeout")._value.get()  # noqa: SLF001
    hits = await retrieve_knowledge_for_node(
        node="plan",
        current_input="做一个塔防游戏",
    )
    after = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "timeout")._value.get()  # noqa: SLF001

    assert hits == []
    assert after == before + 1


@pytest.mark.asyncio
async def test_ingest_rejects_wrong_embedding_dim(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _wrong_dim(_text: str) -> list[float]:
        return [1.0, 0.0]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _wrong_dim)
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 512)

    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 512)

    spec = KnowledgeChunkSpec(
        chunk_id="dim-test",
        text="test chunk",
        domain="design",
        category="gameplay_mechanic",
        title="t",
        source_id="s",
    )
    assert await upsert_knowledge_spec(spec) is False
