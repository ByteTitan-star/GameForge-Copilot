"""Knowledge ingestion pipeline tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.ingest import (
    ingest_corpus,
    ingest_corpus_file,
    load_corpus_file,
    parse_corpus_document,
    upsert_knowledge_spec,
)
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


def test_parse_corpus_document_array_root() -> None:
    data = [
        {
            "chunk_id": "c1",
            "text": "hello",
            "domain": "design",
            "category": "gameplay_mechanic",
            "title": "t",
            "source_id": "s1",
        }
    ]
    specs = parse_corpus_document(data)
    assert len(specs) == 1
    assert specs[0].chunk_id == "c1"


def _corpus_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "app" / "forge" / "knowledge" / "corpus"


def test_load_sample_seed_corpus() -> None:
    chunks = load_corpus_file(_corpus_dir() / "sample_seed.json")
    assert len(chunks) >= 3
    assert {c.domain for c in chunks} <= {"design", "example"}


@pytest.mark.asyncio
async def test_ingest_corpus_dry_run() -> None:
    chunks = load_corpus_file(_corpus_dir() / "sample_seed.json")
    result = await ingest_corpus(chunks, dry_run=True)
    assert result.total == len(chunks)
    assert result.upserted == len(chunks)
    assert result.skipped == 0


@pytest.mark.asyncio
async def test_upsert_knowledge_spec_with_inmemory_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)

    chunks = load_corpus_file(_corpus_dir() / "sample_seed.json")
    ok = await upsert_knowledge_spec(chunks[0])
    assert ok is True
    assert len(store._rows) == 1


@pytest.mark.asyncio
async def test_ingest_corpus_file_integration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)

    async def _fake_embed(text: str) -> list[float]:
        return [0.5, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)

    corpus = tmp_path / "corpus.json"
    corpus.write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_id": "x1",
                        "text": "塔防协同",
                        "domain": "example",
                        "category": "gameplay_case",
                        "title": "案例",
                        "source_id": "test",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = await ingest_corpus_file(corpus)
    assert result.upserted == 1
    assert result.skipped == 0
