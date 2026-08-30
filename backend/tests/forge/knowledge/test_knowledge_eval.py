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
    assert len(cases) >= 4
    assert cases[0].node == "plan"
    negatives = [c for c in cases if c.expect_empty]
    assert len(negatives) >= 2


@pytest.mark.asyncio
async def test_run_eval_with_seeded_store(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryPineconeStore()
    set_knowledge_pinecone_store_override(store)
    monkeypatch.setattr(settings, "knowledge_rag_enabled", True)
    monkeypatch.setattr(settings, "knowledge_rag_inject_plan", True)
    monkeypatch.setattr(settings, "knowledge_semantic_rerank_enabled", False)
    monkeypatch.setattr(settings, "knowledge_min_relevance_score", 0.01)

    async def _fake_embed(text: str) -> list[float]:
        # Positive game queries share a direction; negative domains get orthogonal vec.
        low = text.lower()
        if any(k in text for k in ("甜点", "马卡龙", "对冲", "合规", "金融")) or any(
            k in low for k in ("cooking", "finance")
        ):
            return [0.0, 1.0, 0.0]
        return [1.0, 0.0, 0.5]

    monkeypatch.setattr("app.forge.knowledge.ingest.embed_one", _fake_embed)
    monkeypatch.setattr("app.forge.knowledge.retriever.embed_one", _fake_embed)

    for chunk in load_corpus_file(_corpus_dir() / "sample_seed.json"):
        assert await upsert_knowledge_spec(chunk) is True

    report = await run_eval_cases(load_eval_cases(_corpus_dir() / "eval_queries.json"))
    assert report.total >= 4
    by_id = {r.case_id: r for r in report.results}
    assert by_id["plan-roguelike-td"].ok is True or by_id["plan-platformer"].ok is True
    assert by_id["neg-irrelevant-cuisine"].ok is True
    assert by_id["neg-out-of-corpus-finance"].ok is True
    assert by_id["neg-irrelevant-cuisine"].hit_count == 0
    assert report.passed >= 3
