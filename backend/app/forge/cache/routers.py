"""白名单节点的 Exact Cache 包装（同步纯函数 + Redis get/set + Semantic）。"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from app.enums import EntryPhase
from app.forge.cache.exact import exact_cache_get, exact_cache_set
from app.forge.cache.semantic import (
    semantic_cache_lookup,
    semantic_cache_store,
    semantic_shadow_record,
)
from app.forge.engine_router import normalize_engine_id
from app.forge.entry_router import classify_entry_phase
from app.forge.skills.catalog import catalog_skill_bundle_hash
from app.forge.templates.loader import get_template, list_templates


def _skill_hash() -> str:
    """Skill 变更后 key 失效（进程内 catalog 缓存；部署重启后生效）。"""
    return catalog_skill_bundle_hash()


async def _lookup_caches(
    r: redis.Redis,
    *,
    node: str,
    payload: Any,
    skill_h: str,
) -> Any | None:
    hit = await exact_cache_get(
        r, node=node, input_payload=payload, skill_bundle_hash=skill_h
    )
    if hit is not None:
        return hit
    return await semantic_cache_lookup(
        r, node=node, query=payload, skill_bundle_hash=skill_h
    )


async def _store_caches(
    r: redis.Redis,
    *,
    node: str,
    payload: Any,
    value: Any,
    skill_h: str,
) -> None:
    await exact_cache_set(
        r,
        node=node,
        input_payload=payload,
        value=value,
        skill_bundle_hash=skill_h,
    )
    await semantic_cache_store(
        node=node, query=payload, result=value, skill_bundle_hash=skill_h
    )
    await semantic_shadow_record(r, node=node, query=payload, actual_output=value)


async def classify_entry_phase_cached(
    r: redis.Redis,
    requirement: str | None,
    *,
    has_prior_version: bool,
) -> EntryPhase:
    payload = {
        "requirement": (requirement or "").strip(),
        "has_prior_version": bool(has_prior_version),
    }
    skill_h = _skill_hash()
    hit = await _lookup_caches(
        r, node="entry_router", payload=payload, skill_h=skill_h
    )
    if isinstance(hit, str):
        try:
            return EntryPhase(hit)
        except ValueError:
            pass
    result = classify_entry_phase(requirement, has_prior_version=has_prior_version)
    await _store_caches(
        r, node="entry_router", payload=payload, value=result.value, skill_h=skill_h
    )
    return result


async def normalize_engine_id_cached(r: redis.Redis, value: object) -> str:
    payload = {"value": value if isinstance(value, str) else repr(value)}
    skill_h = _skill_hash()
    hit = await _lookup_caches(
        r, node="engine_router", payload=payload, skill_h=skill_h
    )
    if isinstance(hit, str) and hit:
        return hit
    result = normalize_engine_id(value)
    await _store_caches(
        r, node="engine_router", payload=payload, value=result, skill_h=skill_h
    )
    return result


async def get_template_cached(
    r: redis.Redis,
    template_id: str,
    *,
    require_verified: bool = False,
) -> dict[str, Any]:
    payload = {
        "template_id": template_id,
        "require_verified": bool(require_verified),
    }
    skill_h = _skill_hash()
    hit = await _lookup_caches(
        r, node="template_selection", payload=payload, skill_h=skill_h
    )
    if isinstance(hit, dict) and hit.get("template_id"):
        return hit
    result = get_template(template_id, require_verified=require_verified)
    await _store_caches(
        r, node="template_selection", payload=payload, value=result, skill_h=skill_h
    )
    return result


async def list_templates_cached(
    r: redis.Redis,
    *,
    verified_only: bool = False,
) -> list[dict[str, Any]]:
    payload = {"verified_only": bool(verified_only), "op": "list"}
    skill_h = _skill_hash()
    hit = await _lookup_caches(
        r, node="template_selection", payload=payload, skill_h=skill_h
    )
    if isinstance(hit, list):
        return hit
    result = list_templates(verified_only=verified_only)
    await _store_caches(
        r, node="template_selection", payload=payload, value=result, skill_h=skill_h
    )
    return result
