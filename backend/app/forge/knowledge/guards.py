"""Knowledge RAG 运行时防护（ADR-14 #147 P0）。

【注意】这不是内容审核护栏（guard.py），而是知识库检索侧防护：
  查询长度裁剪、embedding 维度/模型校验、最低相关分过滤。
学内容护栏请走 forge/guard.py 阅读顺序；本文件属 ADR-14 选读。
"""

from __future__ import annotations

from app.core.config import settings
from app.forge.knowledge.types import RetrievedKnowledge


def clip_query_text(text: str, *, max_tokens: int) -> str:
    """按 token 粗估裁剪查询文本，防止 embed 超长。"""
    cleaned = text.strip()
    if not cleaned or max_tokens <= 0:
        return ""
    from app.forge.memory.context_builder import estimate_tokens

    if estimate_tokens(cleaned) <= max_tokens:
        return cleaned
    limit = max(16, max_tokens * 4)
    return cleaned[:limit].rstrip() + "…"


def effective_relevance_score(chunk: RetrievedKnowledge) -> float:
    """语义 rerank 分优先，否则用向量检索分。"""
    if chunk.rerank_score is not None:
        return chunk.rerank_score
    return chunk.retrieval_score


def filter_by_min_relevance(
    chunks: list[RetrievedKnowledge],
    *,
    min_score: float,
) -> list[RetrievedKnowledge]:
    if min_score <= 0:
        return chunks
    return [c for c in chunks if effective_relevance_score(c) >= min_score]


def validate_embedding_dim(vector: list[float]) -> bool:
    expected = int(settings.knowledge_embedding_expected_dim)
    if expected <= 0:
        return True
    return len(vector) == expected


def validate_embedding_model_configured() -> bool:
    expected = settings.knowledge_embedding_expected_model.strip()
    if not expected:
        return True
    return settings.embedding_model.strip() == expected


def current_embedding_version_tag() -> str:
    configured = settings.knowledge_embedding_version.strip()
    if configured:
        return configured
    model = settings.embedding_model.strip()
    return f"{model}:v1" if model else ""


def metadata_embedding_version_matches(meta: dict[str, object]) -> bool:
    expected = settings.knowledge_embedding_version.strip()
    if not expected:
        return True
    stored = meta.get("embedding_version")
    if not isinstance(stored, str) or not stored.strip():
        return False
    return stored.strip() == expected
