"""Runtime reader vs ops writer capability split (#147 P1)."""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.pinecone_store import (
    ReadOnlyKnowledgeStore,
    get_knowledge_reader,
    get_knowledge_writer,
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


def test_reader_has_no_upsert() -> None:
    inner = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(inner)
    reader = get_knowledge_reader()
    assert isinstance(reader, ReadOnlyKnowledgeStore)
    assert not hasattr(reader, "upsert")
    writer = get_knowledge_writer()
    assert writer is inner
    assert hasattr(writer, "upsert")


@pytest.mark.asyncio
async def test_reader_query_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)
    await store.upsert(
        vector_id="v1",
        values=[1.0, 0.0],
        metadata={"text": "hello"},
    )
    reader = get_knowledge_reader()
    assert reader is not None
    matches = await reader.query(values=[1.0, 0.0], top_k=1)
    assert len(matches) == 1
    assert matches[0].id == "v1"


def test_writer_none_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "pinecone_enabled", False)
    assert get_knowledge_writer() is None
    assert get_knowledge_reader() is None
