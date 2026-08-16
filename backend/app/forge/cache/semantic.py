"""P4.5 Semantic Cache：仅 shadow / 标定，禁止未校准 direct hit。"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.forge.cache.exact import is_cacheable_node


def semantic_direct_hit_allowed() -> bool:
    """Go/No-Go：未完成 calibration 前永远 False。"""
    return False


async def semantic_cache_lookup(
    r: redis.Redis,
    *,
    node: str,
    query: Any,
) -> Any | None:
    """生产路径查找：在标定完成前一律 miss（禁止 false direct-hit）。"""
    _ = (r, query)
    if not is_cacheable_node(node):
        return None
    if not semantic_direct_hit_allowed():
        return None
    return None


async def semantic_shadow_record(
    r: redis.Redis,
    *,
    node: str,
    query: Any,
    actual_output: Any,
    similarity: float | None = None,
) -> bool:
    """Shadow：后台记 query/output 指纹与可选相似度，不返回给用户路径。"""
    if not settings.semantic_cache_shadow_enabled:
        return False
    if not is_cacheable_node(node):
        return False
    from app.forge.tracing import observe_subsystem

    payload = {
        "node": node,
        "query_hash": _hash_payload(query),
        "output_hash": _hash_payload(actual_output),
        "similarity": similarity,
        "ts": int(time.time()),
    }
    key = f"forge:semantic:shadow:{node}"
    with observe_subsystem("cache", "semantic_shadow", metadata={"node": node}):
        await r.lpush(key, json.dumps(payload, ensure_ascii=False))
        await r.ltrim(key, 0, 999)
        await r.expire(key, settings.semantic_cache_shadow_ttl_s)
    return True


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
