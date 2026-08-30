"""OpenAI-compat Embedding 客户端（ADR-06）。无 key/base_url 时返回 None。"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import httpx

from app.core.config import settings

log = logging.getLogger(__name__)


def embedding_configured() -> bool:
    return bool(
        settings.embedding_enabled
        and settings.embedding_apikey.strip()
        and settings.embedding_base_url.strip()
        and settings.embedding_model.strip()
    )


async def embed_texts(texts: Sequence[str]) -> list[list[float]] | None:
    """批量 embed；未配置或失败返回 None（调用方视为 semantic miss）。"""
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
    from app.core.http_client import get_http_client

    body = {"model": settings.embedding_model.strip(), "input": cleaned}
    timeout = httpx.Timeout(settings.embedding_timeout_s)
    try:
        client = get_http_client()
        resp = await client.post(url, headers=headers, json=body, timeout=timeout)
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
    rows = await embed_texts([text])
    if not rows:
        return None
    return rows[0]
