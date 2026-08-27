"""Knowledge metadata schema and embedding contract (#147 P0)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.metrics import KNOWLEDGE_RETRIEVE_TOTAL
from app.forge.cache.pinecone_store import InMemoryPineconeStore, VectorMatch
from app.forge.knowledge.guards import (
    current_embedding_version_tag,
    metadata_embedding_version_matches,
    validate_embedding_model_configured,
)
from app.forge.knowledge.ingest import (
    KnowledgeChunkSpec,
    parse_corpus_document,
    upsert_knowledge_spec,
)
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.retriever import retrieve_knowledge_for_node
from app.forge.knowledge.schema import metadata_validation_error
from app.forge.memory.context_builder import estimate_tokens


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


def test_metadata_validation_accepts_valid_design_chunk() -> None:
    assert (
        metadata_validation_error(
            domain="design",
            category="gameplay_mechanic",
            acl="internal",
            quality_tier="gold",
        )
        is None
    )


def test_metadata_validation_rejects_unknown_domain() -> None:
    err = metadata_validation_error(
        domain="unknown",
        category="gameplay_mechanic",
        acl="internal",
    )
    assert err is not None
    assert "domain" in err


def test_metadata_validation_rejects_category_domain_mismatch() -> None:
    err = metadata_validation_error(
        domain="design",
        category="engine_constraint",
        acl="internal",
    )
    assert err is not None
    assert "category" in err


def test_parse_corpus_document_rejects_invalid_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_metadata_validation_enabled", True)
    with pytest.raises(ValueError, match="invalid category"):
        parse_corpus_document(
            [
                {
                    "chunk_id": "x",
                    "text": "t",
                    "domain": "design",
                    "category": "engine_constraint",
                    "title": "t",
                    "source_id": "s",
                }
            ]
        )


def test_current_embedding_version_tag_prefers_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_embedding_version", "bge-small-zh-v1.5:v2")
    assert current_embedding_version_tag() == "bge-small-zh-v1.5:v2"


def test_validate_embedding_model_configured() -> None:
    assert validate_embedding_model_configured() is True


def test_estimate_tokens_counts_cjk_per_character() -> None:
    assert estimate_tokens("塔防游戏") == 4
    assert estimate_tokens("abcd") == 1


@pytest.mark.asyncio
async def test_ingest_writes_embedding_version_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(_text: str) -> list[float]:
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    monkeypatch.setattr(settings, "knowledge_embedding_version", "bge-small-zh-v1.5:v1")
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 0)

    spec = KnowledgeChunkSpec(
        chunk_id="schema-test",
        text="塔防协同",
        domain="design",
        category="gameplay_mechanic",
        title="t",
        source_id="s",
    )
    assert await upsert_knowledge_spec(spec) is True
    _vec, meta = store._rows["schema-test"]
    assert meta["embedding_version"] == "bge-small-zh-v1.5:v1"


@pytest.mark.asyncio
async def test_retrieve_skips_stale_embedding_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(_text: str) -> list[float]:
        return [1.0, 0.0, 0.5]

    async def _stale_query(*_args: object, **_kwargs: object) -> list[VectorMatch]:
        return [
            VectorMatch(
                id="stale",
                score=0.95,
                metadata={
                    "text": "旧版本向量",
                    "domain": "design",
                    "category": "gameplay_mechanic",
                    "title": "stale",
                    "source_id": "s",
                    "acl": "internal",
                    "embedding_version": "bge-small-zh-v1.5:v0",
                },
            )
        ]

    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)
    monkeypatch.setattr(store, "query", _stale_query)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_embedding_version", "bge-small-zh-v1.5:v1")
    monkeypatch.setattr(settings, "knowledge_embedding_expected_dim", 3)
    monkeypatch.setattr(settings, "knowledge_semantic_rerank_enabled", False)
    monkeypatch.setattr(settings, "knowledge_min_relevance_score", 0.0)

    before = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "no_hit")._value.get()  # noqa: SLF001
    hits = await retrieve_knowledge_for_node(
        node="plan",
        current_input="做一个塔防游戏",
    )
    after = KNOWLEDGE_RETRIEVE_TOTAL.labels("plan", "no_hit")._value.get()  # noqa: SLF001

    assert hits == []
    assert after == before + 1
    assert (
        metadata_embedding_version_matches({"embedding_version": "bge-small-zh-v1.5:v0"}) is False
    )
