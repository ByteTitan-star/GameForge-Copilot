"""Knowledge RAG 数据契约（ADR-14 §3.12）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalQuery:
    query_text: str
    domains: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass(frozen=True)
class RetrievedKnowledge:
    chunk_id: str
    domain: str
    category: str
    title: str
    text: str
    retrieval_score: float
    source_id: str
    trust_level: str = "curated"
    rerank_score: float | None = None
