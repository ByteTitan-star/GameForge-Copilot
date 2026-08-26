"""ADR-14 Knowledge RAG tests：双 Index 隔离 + 检索链路。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import (
    HttpPineconeStore,
    get_pinecone_store,
    reset_pinecone_store_override,
)
from app.forge.knowledge.pinecone_store import (
    get_knowledge_pinecone_store,
    knowledge_pinecone_configured,
    reset_knowledge_pinecone_store_override,
)
from app.forge.knowledge.query_builder import build_retrieval_query
from app.forge.knowledge.retriever import (
    knowledge_rag_enabled_for_node,
    retrieve_knowledge_for_node,
)


@pytest.fixture(autouse=True)
def _reset_stores() -> None:
    reset_pinecone_store_override()
    reset_knowledge_pinecone_store_override()
    yield
    reset_pinecone_store_override()
    reset_knowledge_pinecone_store_override()


def test_knowledge_host_does_not_fallback_to_semantic_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(settings, "pinecone_host", "semantic.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "")

    assert knowledge_pinecone_configured() is False
    assert get_knowledge_pinecone_store() is None
    assert isinstance(get_pinecone_store(), HttpPineconeStore)


def test_knowledge_and_semantic_use_different_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(settings, "pinecone_host", "semantic.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "knowledge.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_namespace", "default")
    monkeypatch.setattr(settings, "pinecone_knowledge_namespace", "global")

    cache_store = get_pinecone_store()
    knowledge_store = get_knowledge_pinecone_store()
    assert isinstance(cache_store, HttpPineconeStore)
    assert isinstance(knowledge_store, HttpPineconeStore)
    assert cache_store._host == "semantic.pinecone.io"
    assert knowledge_store._host == "knowledge.pinecone.io"
    assert cache_store._namespace == "default"
    assert knowledge_store._namespace == "global"


def test_knowledge_rag_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "knowledge_rag_enabled", False)
    assert knowledge_rag_enabled_for_node("plan") is False


@pytest.mark.asyncio
async def test_retrieve_noop_when_flag_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "knowledge_rag_enabled", False)
    out = await retrieve_knowledge_for_node(
        node="plan",
        current_input="做一个塔防游戏",
        design_doc={"title": "塔防"},
    )
    assert out == []


def test_query_builder_skips_empty_input() -> None:
    assert build_retrieval_query(node="plan", current_input="   ", design_doc=None) is None


def test_query_builder_includes_design_doc_hints() -> None:
    q = build_retrieval_query(
        node="plan",
        current_input="做一个肉鸽塔防",
        design_doc={"title": "随机塔防", "genre": "roguelike"},
    )
    assert q is not None
    assert "肉鸽塔防" in q.query_text
    assert "随机塔防" in q.query_text
    assert "design" in q.domains
