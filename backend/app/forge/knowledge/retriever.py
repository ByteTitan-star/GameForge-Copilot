"""Knowledge RAG 运行时检索（只读；经 ContextBuilder 注入）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.forge.knowledge.pinecone_store import get_knowledge_pinecone_store
from app.forge.knowledge.policy import policy_for_node
from app.forge.knowledge.query_builder import build_retrieval_query
from app.forge.knowledge.types import RetrievedKnowledge
from app.llm.embeddings import embed_one

log = logging.getLogger(__name__)

_QUALITY_RANK = {"gold": 3, "silver": 2, "bronze": 1}


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
    rerank = score + _QUALITY_RANK.get(tier, 1) * 0.001
    return RetrievedKnowledge(
        chunk_id=chunk_id,
        domain=domain,
        category=category,
        title=title,
        text=text.strip(),
        retrieval_score=score,
        source_id=source_id,
        trust_level=trust,
        rerank_score=rerank,
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
    query = build_retrieval_query(node=node, current_input=current_input, design_doc=design_doc)
    if query is None:
        return []
    store = get_knowledge_pinecone_store()
    if store is None:
        return []
    vector = await embed_one(query.query_text)
    if vector is None:
        return []
    top_k = max(1, int(settings.knowledge_retrieve_k))
    try:
        matches = await store.query(
            values=vector,
            top_k=top_k,
            filter=_metadata_filter(query.domains, query.categories),
        )
    except Exception as exc:  # noqa: BLE001 — RAG 失败降级，不阻断主流程
        log.warning("knowledge retrieve failed: %s", type(exc).__name__)
        return []
    chunks: list[RetrievedKnowledge] = []
    for match in matches:
        parsed = _parse_chunk(match.metadata, score=match.score, chunk_id=match.id)
        if parsed is not None:
            chunks.append(parsed)
    top_n = max(1, int(settings.knowledge_rerank_top_n))
    return _dedupe_and_trim(chunks, top_n=top_n)
