"""Knowledge RAG Prometheus 埋点（ADR-14 §5）。"""

from __future__ import annotations

# ok=注入成功；no_hit=后端正常但无命中；fail=配置/传输/embed 失败；
# degraded=部分降级（如 rerank 失败仍返回结果）；timeout=超时；
# circuit_open=熔断打开，跳过检索（fail-open）
KnowledgeRetrieveStatus = str


def record_knowledge_retrieve(
    node: str,
    *,
    status: KnowledgeRetrieveStatus,
    retrieved_count: int,
    injected_count: int,
    latency_s: float,
    rerank_latency_s: float = 0.0,
) -> None:
    try:
        from app.core.metrics import (
            KNOWLEDGE_RERANK_LATENCY,
            KNOWLEDGE_RETRIEVE_COUNT,
            KNOWLEDGE_RETRIEVE_LATENCY,
            KNOWLEDGE_RETRIEVE_TOTAL,
        )

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


def record_knowledge_rerank_skip(node: str, *, reason: str) -> None:
    try:
        from app.core.metrics import KNOWLEDGE_RERANK_SKIP_TOTAL

        KNOWLEDGE_RERANK_SKIP_TOTAL.labels(node, reason).inc()
    except Exception:  # noqa: BLE001
        return
