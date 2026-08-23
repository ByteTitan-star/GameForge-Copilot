"""OpenAI-compat Embedding 客户端（ADR-06）。无 key/base_url 时返回 None。"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


def embedding_configured() -> bool:
    """检查 Embedding 服务是否已完整配置。

    作用：校验 enabled、apikey、base_url、model 均非空。
    场景：embed_texts 调用前快速判断。
    参数：无。
    返回：已配置为 True，否则 False。
    """
    return bool(
        settings.embedding_enabled
        and settings.embedding_apikey.strip()
        and settings.embedding_base_url.strip()
        and settings.embedding_model.strip()
    )


async def embed_texts(texts: Sequence[str]) -> list[list[float]] | None:
    """批量调用 OpenAI 兼容 Embedding API。

    作用：POST /embeddings 并解析向量列表。
    场景：语义检索、记忆摘要等；未配置或失败时调用方视为 miss。
    参数：texts 字符串序列（空串会被过滤）。
    返回：与输入等长的 float 向量列表；失败或未配置返回 None。
    """
    if not embedding_configured():
        return None
    cleaned = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not cleaned:
        return None
    base = settings.embedding_base_url.rstrip("/")
    url = f"{base}/embeddings"
    headers = {
        "authorization": f"Bearer {settings.embedding_apikey.strip()}",
        "content-type": "application/json",
    }
    body = {"model": settings.embedding_model.strip(), "input": cleaned}
    timeout = httpx.Timeout(settings.embedding_timeout_s)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        log.warning("embedding request failed: %s", type(exc).__name__)
        return None
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list) or len(items) != len(cleaned):
        log.warning("embedding response shape mismatch")
        return None
    out: list[list[float]] = []
    for item in sorted(items, key=lambda x: int(x.get("index", 0))):
        vec = item.get("embedding")
        if not isinstance(vec, list) or not vec:
            return None
        out.append([float(v) for v in vec])
    return out


async def embed_one(text: str) -> list[float] | None:
    """对单条文本做 Embedding。

    作用：封装 embed_texts([text]) 取首向量。
    场景：单条查询向量生成。
    参数：text 待嵌入文本。
    返回：float 向量或 None。
    """
    rows = await embed_texts([text])
    if not rows:
        return None
    return rows[0]
