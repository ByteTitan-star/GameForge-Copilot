"""Knowledge RAG 运行时检索（只读；经 ContextBuilder 注入）。"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.core.config import settings
from app.forge.knowledge.guards import (
    filter_by_min_relevance,
    validate_embedding_dim,
)
from app.forge.knowledge.metrics import record_knowledge_retrieve
from app.forge.knowledge.pinecone_store import get_knowledge_pinecone_store
from app.forge.knowledge.policy import policy_for_node
from app.forge.knowledge.query_builder import build_retrieval_query
from app.forge.knowledge.rerank import apply_semantic_rerank, quality_tie_break
from app.forge.knowledge.types import RetrievedKnowledge
from app.llm.embeddings import embed_one

log = logging.getLogger(__name__)


def knowledge_rag_enabled_for_node(node: str) -> bool:
    if not settings.knowledge_rag_enabled:
        return False
    if node == "plan":
        return settings.knowledge_rag_inject_plan
    if node == "revise":
        return settings.knowledge_rag_inject_revise
    if node in ("art", "art_detail"):
        return settings.knowledge_rag_inject_art
    if node in ("code", "repair"):
        return settings.knowledge_rag_inject_code
    return False


def _metadata_filter(
    query_domains: tuple[str, ...], query_categories: tuple[str, ...]
) -> dict[str, Any]:
    filt: dict[str, Any] = {"acl": {"$in": ["public", "internal"]}}
    if query_domains:
        filt["domain"] = {"$in": list(query_domains)}
    if query_categories:
        filt["category"] = {"$in": list(query_categories)}
    return filt


def _parse_chunk(meta: dict[str, Any], *, score: float, chunk_id: str) -> RetrievedKnowledge | None:
    text = meta.get("text") or meta.get("content") or ""
    if isinstance(text, str) and text.startswith("{") and "text" in text:
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and parsed.get("text"):
                text = str(parsed["text"])
        except json.JSONDecodeError:
            pass
    if not isinstance(text, str) or not text.strip():
        return None
    domain = str(meta.get("domain") or "")
    category = str(meta.get("category") or "")
    title = str(meta.get("title") or chunk_id)
    source_id = str(meta.get("source_id") or "")
    trust = str(meta.get("trust_level") or meta.get("source_kind") or "curated")
    tier = str(meta.get("quality_tier") or "silver")
    tie = quality_tie_break(quality_tier=tier, trust_level=trust)
    return RetrievedKnowledge(
        chunk_id=chunk_id,
        domain=domain,
        category=category,
        title=title,
        text=text.strip(),
        retrieval_score=score,
        source_id=source_id,
        trust_level=trust,
        quality_tier=tier,
        rerank_score=score + tie,
    )


def _dedupe_and_trim(chunks: list[RetrievedKnowledge], *, top_n: int) -> list[RetrievedKnowledge]:
    seen: set[str] = set()
    ranked = sorted(
        chunks,
        key=lambda c: (c.rerank_score or c.retrieval_score, c.retrieval_score),
        reverse=True,
    )
    out: list[RetrievedKnowledge] = []
    for chunk in ranked:
        key = chunk.chunk_id or chunk.source_id
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk)
        if len(out) >= top_n:
            break
    return out


async def _retrieve_knowledge_inner(
    *,
    node: str,
    current_input: str,
    design_doc: dict[str, Any] | None,
) -> tuple[list[RetrievedKnowledge], str, int, float]:
    """执行检索；返回 (注入结果, metrics_status, retrieved_count, rerank_latency_s)。"""
    _ = node
    query = build_retrieval_query(node=node, current_input=current_input, design_doc=design_doc)
    if query is None:
        return [], "no_hit", 0, 0.0

    store = get_knowledge_pinecone_store()
    if store is None:
        log.warning("knowledge retrieve skipped: pinecone not configured")
        return [], "fail", 0, 0.0

    vector = await embed_one(query.query_text)
    if vector is None:
        log.warning("knowledge retrieve failed: embedding unavailable")
        return [], "fail", 0, 0.0
    if not validate_embedding_dim(vector):
        log.warning(
            "knowledge retrieve failed: embedding dim %s != expected %s",
            len(vector),
            settings.knowledge_embedding_expected_dim,
        )
        return [], "fail", 0, 0.0

    top_k = max(1, int(settings.knowledge_retrieve_k))
    try:
        matches = await store.query(
            values=vector,
            top_k=top_k,
            filter=_metadata_filter(query.domains, query.categories),
        )
    except Exception as exc:  # noqa: BLE001 — RAG 失败降级，不阻断主流程
        log.warning("knowledge retrieve failed: %s", type(exc).__name__)
        return [], "fail", 0, 0.0

    chunks: list[RetrievedKnowledge] = []
    for match in matches:
        parsed = _parse_chunk(match.metadata, score=match.score, chunk_id=match.id)
        if parsed is not None:
            chunks.append(parsed)

    status = "ok"
    rerank_latency_s = 0.0
    if settings.knowledge_semantic_rerank_enabled and chunks:
        rerank_started = time.perf_counter()
        reranked = await apply_semantic_rerank(vector, chunks)
        rerank_latency_s = time.perf_counter() - rerank_started
        if reranked is not chunks:
            chunks = reranked
        elif len(chunks) > 1:
            status = "degraded"

    retrieved_count = len(chunks)
    min_score = float(settings.knowledge_min_relevance_score)
    chunks = filter_by_min_relevance(chunks, min_score=min_score)

    top_n = max(1, int(settings.knowledge_rerank_top_n))
    result = _dedupe_and_trim(chunks, top_n=top_n)
    if not result:
        return [], "no_hit", retrieved_count, rerank_latency_s
    return result, status, retrieved_count, rerank_latency_s


async def retrieve_knowledge_for_node(
    *,
    node: str,
    current_input: str,
    design_doc: dict[str, Any] | None = None,
) -> list[RetrievedKnowledge]:
    if not knowledge_rag_enabled_for_node(node):
        return []
    if policy_for_node(node) is None:
        return []

    started = time.perf_counter()
    timeout_s = max(0.0, float(settings.knowledge_retrieve_timeout_s))

    try:
        if timeout_s > 0:
            result, status, retrieved_count, rerank_latency_s = await asyncio.wait_for(
                _retrieve_knowledge_inner(
                    node=node,
                    current_input=current_input,
                    design_doc=design_doc,
                ),
                timeout=timeout_s,
            )
        else:
            result, status, retrieved_count, rerank_latency_s = await _retrieve_knowledge_inner(
                node=node,
                current_input=current_input,
                design_doc=design_doc,
            )
    except TimeoutError:
        log.warning("knowledge retrieve timed out after %.1fs", timeout_s)
        record_knowledge_retrieve(
            node,
            status="timeout",
            retrieved_count=0,
            injected_count=0,
            latency_s=time.perf_counter() - started,
        )
        return []

    record_knowledge_retrieve(
        node,
        status=status,
        retrieved_count=retrieved_count,
        injected_count=len(result),
        latency_s=time.perf_counter() - started,
        rerank_latency_s=rerank_latency_s,
    )
    return result
