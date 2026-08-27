"""Knowledge Pinecone strict transport semantics (#147)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import HttpPineconeStore, PineconeTransportError
from app.forge.knowledge.pinecone_store import get_knowledge_pinecone_store


def test_knowledge_store_uses_strict_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", True)
    monkeypatch.setattr(settings, "pinecone_api_key", "key")
    monkeypatch.setattr(settings, "pinecone_knowledge_host", "knowledge.pinecone.io")
    monkeypatch.setattr(settings, "pinecone_knowledge_namespace", "global")

    store = get_knowledge_pinecone_store()
    assert isinstance(store, HttpPineconeStore)
    assert store._strict_errors is True


@pytest.mark.asyncio
async def test_strict_upsert_raises_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = HttpPineconeStore(
        host="example.pinecone.io",
        api_key="key",
        namespace="global",
        strict_errors=True,
    )

    async def _fail_post(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise PineconeTransportError("simulated outage")

    monkeypatch.setattr(store, "_post", _fail_post)

    with pytest.raises(PineconeTransportError):
        await store.upsert(vector_id="x", values=[1.0], metadata={"text": "t"})


@pytest.mark.asyncio
async def test_cache_store_swallows_http_failure_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = HttpPineconeStore(
        host="example.pinecone.io",
        api_key="key",
        namespace="default",
        strict_errors=False,
    )

    async def _empty_post(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {}

    monkeypatch.setattr(store, "_post", _empty_post)

    await store.upsert(vector_id="x", values=[1.0], metadata={"text": "t"})
