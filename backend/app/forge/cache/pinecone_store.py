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
    ) -> None:
        """写入或更新向量及元数据。

        场景：semantic_cache_store。
        参数：vector_id、values、metadata。
        返回：无。
        """

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """相似度查询 top_k 条向量。

        场景：semantic_cache_lookup。
        参数：values、top_k、可选 filter。
        返回：VectorMatch 列表。
        """


class InMemoryPineconeStore:
    """测试与本地无 Pinecone 时的余弦相似度 mock。"""

    def __init__(self) -> None:
        """初始化进程内向量存储表。

        场景：测试或无 Pinecone 配置时。
        参数：无。
        返回：无。
        """
        self._rows: dict[str, tuple[list[float], dict[str, Any]]] = {}

    async def upsert(
        self,
        *,
        vector_id: str,
        values: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """写入或覆盖一条向量及元数据。

        场景：语义缓存命中后 upsert。
        参数：vector_id、values 嵌入、metadata。
        返回：无。
        """
        self._rows[vector_id] = (list(values), dict(metadata))

    async def query(
        self,
        *,
        values: list[float],
        top_k: int = 1,
        filter: dict[str, Any] | None = None,
    ) -> list[VectorMatch]:
        """按余弦相似度检索 top_k 条向量（进程内 mock）。

        场景：无 Pinecone 配置时的本地语义缓存。
        参数：values 查询向量、top_k、可选 metadata filter。
        返回：VectorMatch 列表，按 score 降序。
        """
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
        """初始化 Pinecone data-plane REST 客户端。

        场景：get_pinecone_store 生产环境。
        参数：host、api_key、namespace。
        返回：无。
        """
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
        """向 Pinecone REST API 写入单条向量。

        场景：语义缓存持久化。
        参数：vector_id、values、metadata（经 _json_safe_meta 序列化）。
        返回：无；HTTP 失败时记录 warning。
        """
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
        """向 Pinecone REST API 发起相似度查询。

        场景：Forge 技能/模板语义缓存检索。
        参数：values、top_k、可选 filter。
        返回：VectorMatch 列表；失败时返回空列表。
        """
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
            meta: dict[str, Any] = m["metadata"] if isinstance(m.get("metadata"), dict) else {}
            out.append(
                VectorMatch(
                    id=str(m.get("id") or ""),
                    score=float(m.get("score") or 0.0),
                    metadata=meta,
                )
            )
        return out

    async def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """Pinecone data-plane POST 请求（httpx 异步）。

        场景：upsert / query 内部调用。
        参数：url、JSON body。
        返回：响应 JSON dict；异常时返回 {}。
        """
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


_UNSET = object()
_override: PineconeStore | None | object = _UNSET


def set_pinecone_store_override(store: PineconeStore | None) -> None:
    """测试注入；传 None 表示强制空操作。"""
    global _override
    _override = store


def reset_pinecone_store_override() -> None:
    """清除测试注入的 PineconeStore 覆盖，恢复配置驱动实例。

    场景：pytest teardown。
    参数：无。
    返回：无。
    """
    global _override
    _override = _UNSET


def pinecone_configured() -> bool:
    """判断 settings 中 Pinecone 是否已完整配置且启用。

    场景：get_pinecone_store 分支判断。
    参数：无。
    返回：enabled + api_key + host 均非空时为 True。
    """
    return bool(
        settings.pinecone_enabled
        and settings.pinecone_api_key.strip()
        and settings.pinecone_host.strip()
    )


def get_pinecone_store() -> PineconeStore | None:
    """获取当前进程应使用的 PineconeStore（覆盖 / HTTP / None）。

    场景：semantic cache routers 入口。
    参数：无。
    返回：PineconeStore 实例；未配置且未注入时 None。
    """
    if _override is not _UNSET:
        return _override  # type: ignore[return-value]
    if not pinecone_configured():
        return None
    return HttpPineconeStore(
        host=settings.pinecone_host.strip(),
        api_key=settings.pinecone_api_key.strip(),
        namespace=settings.pinecone_namespace or "default",
    )


def make_vector_id(*, node: str, skill_bundle_hash: str, query_text: str) -> str:
    """为语义缓存生成确定性向量 id（SHA256 截断）。

    场景：upsert / query 前计算 id。
    参数：node、skill_bundle_hash、query_text。
    返回：40 字符 hex 字符串。
    """
    raw = f"{node}|{skill_bundle_hash}|{query_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _cosine(a: list[float], b: list[float]) -> float:
    """计算两向量的余弦相似度。

    场景：InMemoryPineconeStore.query。
    参数：a、b - 等长浮点列表。
    返回：[-1, 1] 相似度；维数不匹配或零向量时 0。
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _meta_matches(meta: dict[str, Any], filt: dict[str, Any]) -> bool:
    """判断 metadata 是否满足简单等值 filter。

    场景：InMemoryPineconeStore 查询过滤。
    参数：meta - 向量元数据；filt - 键值对 filter。
    返回：全部键值相等时为 True。
    """
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
