"""Pinecone REST 封装 + 进程内 mock（ADR-06；无 SDK 硬依赖）。"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class VectorMatch:
    id: str
    score: float
    metadata: dict[str, Any]


class PineconeStore(Protocol):
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


class InMemoryPineconeStore:
    """测试与本地无 Pinecone 时的余弦相似度 mock。"""

    def __init__(self) -> None:
        self._rows: dict[str, tuple[list[float], dict[str, Any]]] = {}

    async def upsert(
        self,
        *,
        vector_id: str,
        values: list[float],
        metadata: dict[str, Any],
    ) -> None:
        self._rows[vector_id] = (list(values), dict(metadata))

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        scored: list[VectorMatch] = []
        for vid, (vec, meta) in self._rows.items():
            if filter and not _meta_matches(meta, filter):
                continue
            score = _cosine(values, vec)
            scored.append(VectorMatch(id=vid, score=score, metadata=meta))
        scored.sort(key=lambda m: m.score, reverse=True)
        return scored[: max(1, top_k)]


class HttpPineconeStore:
    """Pinecone data-plane REST（需 host + api_key）。"""

    def __init__(self, *, host: str, api_key: str, namespace: str) -> None:
        self._host = host.rstrip("/").removeprefix("https://").removeprefix("http://")
        self._api_key = api_key
        self._namespace = namespace

    async def upsert(
        self,
        *,
        vector_id: str,
        values: list[float],
        metadata: dict[str, Any],
    ) -> None:
        url = f"https://{self._host}/vectors/upsert"
        body = {
            "namespace": self._namespace,
            "vectors": [
                {
                    "id": vector_id,
                    "values": values,
                    "metadata": _json_safe_meta(metadata),
                }
            ],
        }
        await self._post(url, body)

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        url = f"https://{self._host}/query"
        body: dict[str, Any] = {
            "namespace": self._namespace,
            "vector": values,
            "topK": max(1, top_k),
            "includeMetadata": True,
        }
        if filter:
            body["filter"] = filter
        data = await self._post(url, body)
        matches = data.get("matches") if isinstance(data, dict) else None
        if not isinstance(matches, list):
            return []
        out: list[VectorMatch] = []
        for m in matches:
            if not isinstance(m, dict):
                continue
            meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
            out.append(
                VectorMatch(
                    id=str(m.get("id") or ""),
                    score=float(m.get("score") or 0.0),
                    metadata=meta,
                )
            )
        return out

    async def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Api-Key": self._api_key,
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, dict) else {}
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("pinecone request failed: %s", type(exc).__name__)
            return {}


_override: PineconeStore | None | object = object()


def set_pinecone_store_override(store: PineconeStore | None) -> None:
    """测试注入；传 None 表示强制空操作。"""
    global _override
    _override = store


def reset_pinecone_store_override() -> None:
    global _override
    _override = object()


def pinecone_configured() -> bool:
    return bool(
        settings.pinecone_enabled
        and settings.pinecone_api_key.strip()
        and settings.pinecone_host.strip()
    )


def get_pinecone_store() -> PineconeStore | None:
    if _override is not object():
        return _override  # type: ignore[return-value]
    if not pinecone_configured():
        return None
    return HttpPineconeStore(
        host=settings.pinecone_host.strip(),
        api_key=settings.pinecone_api_key.strip(),
        namespace=settings.pinecone_namespace or "default",
    )


def make_vector_id(*, node: str, skill_bundle_hash: str, query_text: str) -> str:
    raw = f"{node}|{skill_bundle_hash}|{query_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _meta_matches(meta: dict[str, Any], filt: dict[str, Any]) -> bool:
    return all(meta.get(k) == v for k, v in filt.items())


def _json_safe_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Pinecone metadata 仅允许标量；result 以 JSON 字符串存。"""
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            out[k] = v if v is not None else ""
        else:
            out[k] = json.dumps(v, ensure_ascii=False, default=str)
    if "created_at" not in out:
        out["created_at"] = int(time.time())
    return out
