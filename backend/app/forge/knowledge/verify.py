"""Post-ingest retrieval smoke check."""

from __future__ import annotations

from app.core.config import settings
from app.forge.knowledge.ingest import KnowledgeChunkSpec
from app.forge.knowledge.retriever import retrieve_knowledge_for_node


async def verify_knowledge_retrieval(
    chunks: list[KnowledgeChunkSpec],
    *,
    node: str = "plan",
) -> tuple[bool, str]:
    """用首条 chunk 文本做 plan 节点检索；返回 (ok, detail)。"""
    if not chunks:
        return False, "no chunks to verify"
    sample = next((c for c in chunks if c.text.strip()), None)
    if sample is None:
        return False, "no non-empty chunk text"

    prev_enabled = settings.knowledge_rag_enabled
    prev_plan = settings.knowledge_rag_inject_plan
    settings.knowledge_rag_enabled = True
    settings.knowledge_rag_inject_plan = True
    try:
        hits = await retrieve_knowledge_for_node(
            node=node,
            current_input=sample.text[:200],
            design_doc={"title": sample.title, "genre": sample.domain},
        )
    finally:
        settings.knowledge_rag_enabled = prev_enabled
        settings.knowledge_rag_inject_plan = prev_plan

    if not hits:
        return False, f"retrieve returned 0 hits for chunk_id={sample.chunk_id}"
    titles = ", ".join(h.title for h in hits[:3])
    return True, f"hits={len(hits)} titles={titles}"
