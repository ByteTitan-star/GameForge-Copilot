"""P4 Exact Cache：白名单节点 Redis 精确缓存。

允许：entry_router / engine_router / intent_classification / template_selection /
deterministic_metadata。
禁止：plan / art / code / repair / qa / preference / HITL revise。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import settings

ALLOWLIST: frozenset[str] = frozenset(
    {
        "entry_router",
        "engine_router",
        "intent_classification",
        "template_selection",
        "deterministic_metadata",
    }
)

FORBIDDEN: frozenset[str] = frozenset(
    {
        "plan",
        "art",
        "art_options",
        "art_detail",
        "code",
        "repair",
        "qa",
        "diagnose",
        "preference_extraction",
        "hitl_revise",
        "revise_plan",
        "revise_art_options",
    }
)

PROMPT_VERSION = "v1"
POLICY_VERSION = "v1"


def is_cacheable_node(node: str) -> bool:
    n = (node or "").strip()
    if n in FORBIDDEN:
        return False
    return n in ALLOWLIST


def build_exact_cache_key(
    *,
    node: str,
    input_payload: Any,
    model: str = "",
    prompt_version: str = PROMPT_VERSION,
    policy_version: str = POLICY_VERSION,
    skill_bundle_hash: str = "",
    preference_revision: str | None = None,
) -> str:
    """Cache key：node + input_hash + model + prompt/policy/skill（+ optional pref）。"""
    raw = json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str)
    input_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    parts = [
        "forge:exact",
        node,
        input_hash,
        model or "-",
        prompt_version,
        policy_version,
        skill_bundle_hash or "-",
    ]
    if preference_revision is not None:
        parts.append(preference_revision)
    return ":".join(parts)


async def exact_cache_get(
    r: redis.Redis,
    *,
    node: str,
    input_payload: Any,
    model: str = "",
    skill_bundle_hash: str = "",
    preference_revision: str | None = None,
) -> Any | None:
    if not settings.exact_cache_enabled or not is_cacheable_node(node):
        return None
    key = build_exact_cache_key(
        node=node,
        input_payload=input_payload,
        model=model,
        skill_bundle_hash=skill_bundle_hash,
        preference_revision=preference_revision,
    )
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def exact_cache_set(
    r: redis.Redis,
    *,
    node: str,
    input_payload: Any,
    value: Any,
    model: str = "",
    skill_bundle_hash: str = "",
    preference_revision: str | None = None,
    ttl_s: int | None = None,
) -> bool:
    """写入成功返回 True；禁止节点或关 flag 时返回 False（且不写）。"""
    if not settings.exact_cache_enabled or not is_cacheable_node(node):
        return False
    key = build_exact_cache_key(
        node=node,
        input_payload=input_payload,
        model=model,
        skill_bundle_hash=skill_bundle_hash,
        preference_revision=preference_revision,
    )
    ttl = ttl_s if ttl_s is not None else settings.exact_cache_ttl_s
    await r.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
    return True
