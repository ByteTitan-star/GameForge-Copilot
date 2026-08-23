"""ADR-06 Semantic Cache：Pinecone 分层命中 + Redis shadow。"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

import redis.asyncio as redis

from app.core.config import settings
from app.forge.cache.exact import is_cacheable_node
from app.forge.cache.pinecone_store import (
    get_pinecone_store,
    make_vector_id,
)
from app.llm.embeddings import embed_one

log = logging.getLogger(__name__)


def semantic_direct_hit_allowed() -> bool:
    """分层命中总开关；无 Pinecone/embed 时 lookup 仍会 miss。"""
    return bool(settings.semantic_cache_direct_hit_enabled)


def normalize_query_text(query: Any) -> str:
    """将缓存查询规范为可嵌入的字符串（str strip 或 JSON 序列化）。

    场景：semantic_cache_lookup/store。
    参数：query - 任意可缓存输入。
    返回：规范化查询文本。
    """
    if isinstance(query, str):
        return query.strip()
    return json.dumps(query, ensure_ascii=False, sort_keys=True, default=str)


async def semantic_cache_lookup(
    r: redis.Redis,
    *,
    node: str,
    query: Any,
    skill_bundle_hash: str = "",
) -> Any | None:
    """按相似度分层：miss / soft(LLM 确认) / hard(直接返回)。"""
    _ = r
    if not is_cacheable_node(node):
        return None
    if not semantic_direct_hit_allowed():
        return None
    store = get_pinecone_store()
    if store is None:
        return None
    query_text = normalize_query_text(query)
    if not query_text:
        return None
    vector = await embed_one(query_text)
    if vector is None:
        return None
    filt: dict[str, Any] = {"node": node}
    if skill_bundle_hash:
        filt["skill_bundle_hash"] = skill_bundle_hash
    matches = await store.query(values=vector, top_k=1, filter=filt)
    if not matches:
        return None
    top = matches[0]
    soft = float(settings.semantic_cache_soft_threshold)
    hard = float(settings.semantic_cache_hard_threshold)
    if top.score < soft:
        return None
    result = _parse_result_meta(top.metadata)
    if result is None:
        return None
    if top.score >= hard:
        return result
    confirmed = await _confirm_soft_hit(
        node=node, query_text=query_text, cached_result=result, score=top.score
    )
    return confirmed


async def semantic_cache_store(
    *,
    node: str,
    query: Any,
    result: Any,
    skill_bundle_hash: str = "",
) -> bool:
    """计算完成后写入 Pinecone（Exact 由调用方单独 set）。"""
    if not is_cacheable_node(node):
        return False
    if not semantic_direct_hit_allowed():
        return False
    store = get_pinecone_store()
    if store is None:
        return False
    query_text = normalize_query_text(query)
    vector = await embed_one(query_text)
    if vector is None:
        return False
    vid = make_vector_id(node=node, skill_bundle_hash=skill_bundle_hash, query_text=query_text)
    meta = {
        "node": node,
        "skill_bundle_hash": skill_bundle_hash or "",
        "query_text": query_text[:2000],
        "result": result,
        "created_at": int(time.time()),
    }
    await store.upsert(vector_id=vid, values=vector, metadata=meta)
    return True


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
        await r.lpush(key, json.dumps(payload, ensure_ascii=False))  # type: ignore[misc]
        await r.ltrim(key, 0, 999)  # type: ignore[misc]
        await r.expire(key, settings.semantic_cache_shadow_ttl_s)
    return True


def _parse_result_meta(meta: dict[str, Any]) -> Any | None:
    """从 Pinecone metadata 解析缓存 result 字段。

    场景：semantic_cache_lookup 命中后。
    参数：meta - 向量元数据。
    返回：反序列化后的 result 或 None。
    """
    raw = meta.get("result")
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw


async def _confirm_soft_hit(
    *,
    node: str,
    query_text: str,
    cached_result: Any,
    score: float,
) -> Any | None:
    """[soft, hard) 带：轻量 LLM 确认/适配一次。"""
    provider, model, apikey, base_url = _confirm_llm_cfg()
    if not model or not apikey:
        log.info("semantic soft-hit skipped: confirm LLM not configured")
        return None
    from app.enums import LLMProvider
    from app.llm.platform_complete import platform_complete

    system = (
        "你是缓存确认器。根据当前 query 与候选缓存结果，输出该节点应返回的最终 JSON。"
        '格式：{"ok":true,"result":...} 或 {"ok":false}。只输出 JSON。'
    )
    user_msg = json.dumps(
        {
            "node": node,
            "score": score,
            "query": query_text,
            "cached_result": cached_result,
        },
        ensure_ascii=False,
        default=str,
    )
    try:
        content, _usage = await platform_complete(
            LLMProvider(provider),
            apikey,
            model,
            system,
            user_msg,
            kind="semantic_confirm",
            base_url=base_url or None,
            max_tokens=512,
            metadata={"node": node},
            tags=["forge", "cache"],
        )
    except Exception as exc:  # noqa: BLE001 — 软命中失败则 miss
        log.warning("semantic confirm LLM failed: %s", type(exc).__name__)
        return None
    return _parse_confirm_content(content)


def _confirm_llm_cfg() -> tuple[str, str, str, str]:
    """读取软命中确认用 LLM 的 provider/model/apikey/base_url。

    场景：_confirm_soft_hit。
    参数：无（读 settings，semantic_confirm 优先于 preference_extract）。
    返回：四元组配置。
    """
    if settings.semantic_confirm_model.strip():
        return (
            settings.semantic_confirm_provider,
            settings.semantic_confirm_model.strip(),
            settings.semantic_confirm_apikey.strip() or settings.preference_extract_apikey.strip(),
            settings.semantic_confirm_base_url.strip()
            or settings.preference_extract_base_url.strip(),
        )
    return (
        settings.preference_extract_provider,
        settings.preference_extract_model.strip(),
        settings.preference_extract_apikey.strip(),
        settings.preference_extract_base_url.strip(),
    )


def _parse_confirm_content(content: str) -> Any | None:
    """解析确认 LLM 返回的 {\"ok\":true,\"result\":...} JSON。

    场景：_confirm_soft_hit 成功后。
    参数：content - LLM 原始输出。
    返回：result 字段或 None（未确认）。
    """
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    return data.get("result")


def _hash_payload(value: Any) -> str:
    """对任意 payload 做确定性 SHA256 截断哈希。

    场景：semantic_shadow_record 记录 query/output 指纹。
    参数：value - 可 JSON 序列化对象。
    返回：24 字符 hex。
    """
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
