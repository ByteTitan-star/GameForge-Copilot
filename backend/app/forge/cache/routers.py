"""白名单节点的 Exact Cache 包装（同步纯函数 + Redis get/set）。"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis

from app.enums import EntryPhase
from app.forge.cache.exact import exact_cache_get, exact_cache_set
from app.forge.engine_router import normalize_engine_id
from app.forge.entry_router import classify_entry_phase
from app.forge.templates.loader import get_template, list_templates


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
    hit = await exact_cache_get(r, node="entry_router", input_payload=payload)
    if isinstance(hit, str):
        try:
            return EntryPhase(hit)
        except ValueError:
            pass
    result = classify_entry_phase(requirement, has_prior_version=has_prior_version)
    await exact_cache_set(
        r, node="entry_router", input_payload=payload, value=result.value
    )
    return result


async def normalize_engine_id_cached(r: redis.Redis, value: object) -> str:
    payload = {"value": value if isinstance(value, str) else repr(value)}
    hit = await exact_cache_get(r, node="engine_router", input_payload=payload)
    if isinstance(hit, str) and hit:
        return hit
    result = normalize_engine_id(value)
    await exact_cache_set(r, node="engine_router", input_payload=payload, value=result)
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
    hit = await exact_cache_get(r, node="template_selection", input_payload=payload)
    if isinstance(hit, dict) and hit.get("template_id"):
        return hit
    result = get_template(template_id, require_verified=require_verified)
    await exact_cache_set(r, node="template_selection", input_payload=payload, value=result)
    return result


async def list_templates_cached(
    r: redis.Redis,
    *,
    verified_only: bool = False,
) -> list[dict[str, Any]]:
    payload = {"verified_only": bool(verified_only), "op": "list"}
    hit = await exact_cache_get(r, node="template_selection", input_payload=payload)
    if isinstance(hit, list):
        return hit
    result = list_templates(verified_only=verified_only)
    await exact_cache_set(r, node="template_selection", input_payload=payload, value=result)
    return result
