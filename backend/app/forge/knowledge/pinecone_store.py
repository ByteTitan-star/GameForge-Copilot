"""Knowledge Index 专用 Pinecone 客户端（ADR-14 §3.1.1；禁止复用 semantic cache factory）。

P1：Runtime 只读 Reader vs Ops Writer 能力拆分——retriever 不得持有 upsert。
"""

from __future__ import annotations

from typing import Any, Protocol

from app.core.config import settings
from app.forge.cache.pinecone_store import HttpPineconeStore, InMemoryPineconeStore, VectorMatch

_KnowledgeStore = HttpPineconeStore | InMemoryPineconeStore

_UNSET = object()
_override: _KnowledgeStore | None | object = _UNSET


class KnowledgeVectorReader(Protocol):
    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...


class KnowledgeVectorWriter(Protocol):
    async def upsert(
        self,
        *,
        vector_id: str,
        values: list[float],
        metadata: dict[str, Any],
    ) -> None: ...

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]: ...


class ReadOnlyKnowledgeStore:
    """包装底层 store，仅暴露 query（Runtime Agent 路径）。"""

    def __init__(self, inner: KnowledgeVectorWriter) -> None:
        self._inner = inner

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        return await self._inner.query(values=values, top_k=top_k, filter=filter)


# 兼容旧名
KnowledgePineconeStore = KnowledgeVectorWriter


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
    """底层全能力 store（测试 / 兼容）；生产路径请用 reader/writer。"""
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


def get_knowledge_reader() -> KnowledgeVectorReader | None:
    store = get_knowledge_pinecone_store()
    if store is None:
        return None
    return ReadOnlyKnowledgeStore(store)


def get_knowledge_writer() -> KnowledgeVectorWriter | None:
    return get_knowledge_pinecone_store()
