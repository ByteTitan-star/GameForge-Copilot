"""Knowledge RAG eval tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.forge.cache.pinecone_store import InMemoryPineconeStore
from app.forge.knowledge.eval import load_eval_cases, run_eval_cases
from app.forge.knowledge.ingest import load_corpus_file, upsert_knowledge_spec
from app.forge.knowledge.pinecone_store import (
    reset_knowledge_pinecone_store_override,
    set_knowledge_pinecone_store_override,
)


def _corpus_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "app" / "forge" / "knowledge" / "corpus"


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_knowledge_pinecone_store_override()
    yield
    reset_knowledge_pinecone_store_override()


def test_load_eval_cases() -> None:
    cases = load_eval_cases(_corpus_dir() / "eval_queries.json")
    assert len(cases) >= 2
    assert cases[0].node == "plan"


@pytest.mark.asyncio
async def test_run_eval_with_seeded_store(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)

    async def _fake_embed(text: str) -> list[float]:
        _ = text
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)

    for chunk in load_corpus_file(_corpus_dir() / "sample_seed.json"):
        assert await upsert_knowledge_spec(chunk) is True

    report = await run_eval_cases(load_eval_cases(_corpus_dir() / "eval_queries.json"))
    assert report.total >= 2
    assert report.passed >= 1
