"""Transport fault injection for Knowledge Pinecone / embedding (#147 P1)."""

from __future__ import annotations

import httpx
import pytest

from app.core import http_client
from app.core.config import settings
from app.forge.cache.pinecone_store import HttpPineconeStore, PineconeTransportError
from app.forge.knowledge.circuit import reset_knowledge_circuit
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)
from app.forge.knowledge.retriever import retrieve_knowledge_for_node
from app.llm import embeddings


@pytest.fixture(autouse=True)
async def _reset() -> None:
    reset_knowledge_circuit()
    reset_knowledge_pinecone_store_override()
    await http_client.aclose_http_client()
    yield
    reset_knowledge_circuit()
    reset_knowledge_pinecone_store_override()
    await http_client.aclose_http_client()


def _mock_transport(handler):  # type: ignore[no-untyped-def]
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_strict_pinecone_raises_on_http_500() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"message": "boom"})

    transport = _mock_transport(handler)
    client = httpx.AsyncClient(transport=transport, trust_env=False)
    http_client.reset_http_client_for_tests()
    # inject mock via monkeypatch on get_http_client
    import app.core.http_client as hc

    original = hc.get_http_client
    hc._client = client  # type: ignore[attr-defined]

    store = HttpPineconeStore(
        host="example.pinecone.io",
        api_key="key",
        namespace="global",
        strict_errors=True,
    )
    with pytest.raises(PineconeTransportError):
        await store.query(values=[0.1, 0.2], top_k=1)

    await client.aclose()
    hc._client = None  # type: ignore[attr-defined]
    _ = original


@pytest.mark.asyncio
async def test_strict_pinecone_raises_on_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport = _mock_transport(handler)
    client = httpx.AsyncClient(transport=transport, trust_env=False)
    import app.core.http_client as hc

    hc._client = client  # type: ignore[attr-defined]

    store = HttpPineconeStore(
        host="example.pinecone.io",
        api_key="key",
        namespace="global",
        strict_errors=True,
    )
    with pytest.raises(PineconeTransportError):
        await store.upsert(vector_id="x", values=[1.0], metadata={"text": "t"})

    await client.aclose()
    hc._client = None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_embed_returns_none_on_http_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "embedding_enabled", True)
    monkeypatch.setattr(settings, "embedding_apikey", "k")
    monkeypatch.setattr(settings, "embedding_base_url", "http://tei.local/v1")
    monkeypatch.setattr(settings, "embedding_model", "m")
    monkeypatch.setattr(settings, "embedding_timeout_s", 5)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate"})

    client = httpx.AsyncClient(transport=_mock_transport(handler), trust_env=False)
    import app.core.http_client as hc

    hc._client = client  # type: ignore[attr-defined]
    assert await embeddings.embed_texts(["hello"]) is None
    await client.aclose()
    hc._client = None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_retrieve_fail_open_when_store_query_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BoomStore:
        async def query(self, *args: object, **kwargs: object) -> list[object]:
            raise PineconeTransportError("injected")

        async def upsert(self, *args: object, **kwargs: object) -> None:
            raise AssertionError("runtime must not upsert")

    set_knowledge_pinecone_store_override(BoomStore())  # type: ignore[arg-type]
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_circuit_enabled", False)

    async def _fake_embed(text: str) -> list[float]:
        return [1.0, 0.0]

    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)
    monkeypatch.setattr(
        "app.forge.knowledge.retriever.validate_embedding_model_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.forge.knowledge.retriever.validate_embedding_dim",
        lambda _v: True,
    )

    out = await retrieve_knowledge_for_node(
        node="plan",
        current_input="塔防设计",
        design_doc={"title": "塔防"},
    )
    assert out == []
