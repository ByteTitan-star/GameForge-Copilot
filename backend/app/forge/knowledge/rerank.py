"""Knowledge RAG 语义 Rerank（ADR-14 §3.10 R1）。

#147 P1 成本结论：同模型二次 embed 与 Pinecone cosine 高度冗余。
默认仍可用开关开启；当 top1−top2 retrieval_score 差距足够大时跳过二次 embed，
仅依赖 retrieval_score + quality_tie_break。
"""

from __future__ import annotations

import math
from dataclasses import replace

from app.forge.knowledge.types import RetrievedKnowledge
from app.llm.embeddings import embed_texts

_TIER_RANK = {"gold": 3, "silver": 2, "bronze": 1}


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def quality_tie_break(*, quality_tier: str, trust_level: str) -> float:
    """Quality / Trust 同尺度 tie-break（小量加成，不压过语义分）。"""
    tier = _TIER_RANK.get(quality_tier, 1)
    trust = 0.0002 if trust_level in ("curated", "internal") else 0.0
    return tier * 0.0001 + trust


def should_skip_semantic_rerank(
    chunks: list[RetrievedKnowledge],
    *,
    min_gap: float,
) -> bool:
    """top1 与 top2 检索分差 ≥ min_gap 时跳过同模型二次 embed。"""
    if min_gap <= 0 or len(chunks) < 2:
        return False
    ranked = sorted(chunks, key=lambda c: c.retrieval_score, reverse=True)
    return (ranked[0].retrieval_score - ranked[1].retrieval_score) >= min_gap


async def apply_semantic_rerank(
    query_vector: list[float],
    chunks: list[RetrievedKnowledge],
) -> list[RetrievedKnowledge]:
    """用 query 向量与 chunk 文本 embedding 余弦相似度重排。"""
    if not chunks:
        return []
    vectors = await embed_texts([c.text for c in chunks])
    if vectors is None or len(vectors) != len(chunks):
        return chunks
    reranked: list[RetrievedKnowledge] = []
    for chunk, vec in zip(chunks, vectors, strict=True):
        semantic = _cosine(query_vector, vec)
        tie = quality_tie_break(
            quality_tier=chunk.quality_tier,
            trust_level=chunk.trust_level,
        )
        reranked.append(replace(chunk, rerank_score=semantic + tie))
    return sorted(
        reranked,
        key=lambda c: (c.rerank_score or 0.0, c.retrieval_score),
        reverse=True,
    )
