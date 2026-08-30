"""Knowledge semantic rerank tests."""

from __future__ import annotations

import pytest

from app.forge.knowledge.rerank import apply_semantic_rerank, quality_tie_break
from app.forge.knowledge.types import RetrievedKnowledge


def _chunk(chunk_id: str, text: str, *, tier: str = "silver") -> RetrievedKnowledge:
    return RetrievedKnowledge(
        chunk_id=chunk_id,
        domain="design",
        category="gameplay_mechanic",
        title=chunk_id,
        text=text,
        retrieval_score=0.5,
        source_id="test",
        quality_tier=tier,
        rerank_score=0.5,
    )


def test_quality_tie_break_prefers_gold() -> None:
    gold = quality_tie_break(quality_tier="gold", trust_level="curated")
    silver = quality_tie_break(quality_tier="silver", trust_level="curated")
    assert gold > silver


def test_should_skip_semantic_rerank_when_gap_large() -> None:
    from app.forge.knowledge.rerank import should_skip_semantic_rerank

    chunks = [
        _chunk("a", "x"),
        _chunk("b", "y"),
    ]
    chunks[0] = RetrievedKnowledge(
        chunk_id="a",
        domain="design",
        category="gameplay_mechanic",
        title="a",
        text="x",
        retrieval_score=0.95,
        source_id="test",
        quality_tier="silver",
        rerank_score=0.95,
    )
    chunks[1] = RetrievedKnowledge(
        chunk_id="b",
        domain="design",
        category="gameplay_mechanic",
        title="b",
        text="y",
        retrieval_score=0.50,
        source_id="test",
        quality_tier="silver",
        rerank_score=0.50,
    )
    assert should_skip_semantic_rerank(chunks, min_gap=0.12) is True
    assert should_skip_semantic_rerank(chunks, min_gap=0.50) is False


@pytest.mark.asyncio
async def test_semantic_rerank_orders_by_embedding_similarity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_vec = [1.0, 0.0, 0.0]
    chunks = [
        _chunk("a", "unrelated topic"),
        _chunk("b", "matching gameplay design"),
    ]

    async def _fake_embed(texts: list[str]) -> list[list[float]] | None:
        out: list[list[float]] = []
        for text in texts:
            if "matching" in text:
                out.append([0.9, 0.1, 0.0])
            else:
                out.append([0.1, 0.9, 0.0])
        return out

    monkeypatch.setattr("app.forge.knowledge.rerank.embed_texts", _fake_embed)
    reranked = await apply_semantic_rerank(query_vec, chunks)
    assert reranked[0].chunk_id == "b"
    assert (reranked[0].rerank_score or 0) > (reranked[1].rerank_score or 0)
