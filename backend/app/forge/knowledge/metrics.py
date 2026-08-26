"""Knowledge RAG Prometheus 埋点（ADR-14 §5）。"""

from __future__ import annotations


def record_knowledge_retrieve(
    node: str,
    *,
    ok: bool,
    retrieved_count: int,
    injected_count: int,
    latency_s: float,
    rerank_latency_s: float = 0.0,
    degraded: bool = False,
) -> None:
    try:
        from app.core.metrics import (
            KNOWLEDGE_RERANK_LATENCY,
            KNOWLEDGE_RETRIEVE_COUNT,
            KNOWLEDGE_RETRIEVE_LATENCY,
            KNOWLEDGE_RETRIEVE_TOTAL,
        )

        status = "ok" if ok and not degraded else "degraded" if degraded else "fail"
        KNOWLEDGE_RETRIEVE_TOTAL.labels(node, status).inc()
        KNOWLEDGE_RETRIEVE_LATENCY.labels(node).observe(max(latency_s, 0.0))
        if retrieved_count > 0:
            KNOWLEDGE_RETRIEVE_COUNT.labels(node).observe(retrieved_count)
        if rerank_latency_s > 0:
            KNOWLEDGE_RERANK_LATENCY.labels(node).observe(rerank_latency_s)
        if injected_count > 0:
            KNOWLEDGE_RETRIEVE_COUNT.labels(f"{node}_injected").observe(injected_count)
    except Exception:  # noqa: BLE001
        return
