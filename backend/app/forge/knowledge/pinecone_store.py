"""Knowledge Index 专用 Pinecone 客户端（ADR-14 §3.1.1；禁止复用 semantic cache factory）。"""

from __future__ import annotations

from typing import Protocol

from app.core.config import settings
from app.forge.cache.pinecone_store import HttpPineconeStore, InMemoryPineconeStore

_KnowledgeStore = HttpPineconeStore | InMemoryPineconeStore

_UNSET = object()
_override: _KnowledgeStore | None | object = _UNSET


class KnowledgePineconeStore(Protocol):
    async def upsert(
        self,
        *,
        vector_id: str,
        values: list[float],
        metadata: dict,
    ) -> None: ...

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict | None = None,
    ) -> list: ...


def set_knowledge_pinecone_store_override(store: _KnowledgeStore | None) -> None:
    global _override
    _override = store


def reset_knowledge_pinecone_store_override() -> None:
    global _override
    _override = _UNSET


def knowledge_pinecone_configured() -> bool:
    """Knowledge host 必须显式配置；禁止 fallback 到 semantic cache host。"""
    return bool(
        settings.pinecone_enabled
        and settings.pinecone_api_key.strip()
        and settings.pinecone_knowledge_host.strip()
    )


def get_knowledge_pinecone_store() -> _KnowledgeStore | None:
    if _override is not _UNSET:
        return _override  # type: ignore[return-value]
    if not knowledge_pinecone_configured():
        return None
    return HttpPineconeStore(
        host=settings.pinecone_knowledge_host.strip(),
        api_key=settings.pinecone_api_key.strip(),
        namespace=settings.pinecone_knowledge_namespace or "global",
        strict_errors=True,
    )
