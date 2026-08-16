"""P4 Exact Cache：白名单强制 + Redis get/set + 路由包装。"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from app.core.config import settings
from app.enums import EntryPhase
from app.forge.cache.exact import (
    ALLOWLIST,
    FORBIDDEN,
    build_exact_cache_key,
    exact_cache_get,
    exact_cache_set,
    is_cacheable_node,
)
from app.forge.cache.routers import (
    classify_entry_phase_cached,
    get_template_cached,
    normalize_engine_id_cached,
)


@pytest.fixture
def redis_client() -> fakeredis.aioredis.FakeRedis:
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


def test_allowlist_and_forbidden_disjoint() -> None:
    assert ALLOWLIST.isdisjoint(FORBIDDEN)
    for node in ("plan", "art", "code", "repair", "qa", "preference_extraction", "hitl_revise"):
        assert node in FORBIDDEN
        assert not is_cacheable_node(node)
    for node in ("entry_router", "engine_router", "template_selection"):
        assert node in ALLOWLIST
        assert is_cacheable_node(node)


def test_cache_key_includes_skill_and_optional_pref() -> None:
    base = build_exact_cache_key(
        node="entry_router",
        input_payload={"a": 1},
        model="m1",
        skill_bundle_hash="abc",
    )
    with_pref = build_exact_cache_key(
        node="entry_router",
        input_payload={"a": 1},
        model="m1",
        skill_bundle_hash="abc",
        preference_revision="r2",
    )
    assert "entry_router" in base
    assert "abc" in base
    assert with_pref != base
    assert with_pref.endswith(":r2")


@pytest.mark.asyncio
async def test_forbidden_nodes_never_write(redis_client: fakeredis.aioredis.FakeRedis) -> None:
    for node in ("plan", "code", "art", "repair", "qa", "preference_extraction"):
        ok = await exact_cache_set(
            redis_client,
            node=node,
            input_payload={"x": 1},
            value={"bad": True},
        )
        assert ok is False
        assert await exact_cache_get(redis_client, node=node, input_payload={"x": 1}) is None
    keys = await redis_client.keys("forge:exact:*")
    assert keys == []


@pytest.mark.asyncio
async def test_exact_cache_roundtrip_allowlist(
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    payload = {"requirement": "把背景改成紫色", "has_prior_version": True}
    assert await exact_cache_get(redis_client, node="entry_router", input_payload=payload) is None
    assert await exact_cache_set(
        redis_client, node="entry_router", input_payload=payload, value="code"
    )
    assert await exact_cache_get(redis_client, node="entry_router", input_payload=payload) == "code"


@pytest.mark.asyncio
async def test_exact_cache_disabled_skips(
    redis_client: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "exact_cache_enabled", False)
    assert not await exact_cache_set(
        redis_client, node="entry_router", input_payload={"a": 1}, value="plan"
    )
    assert await exact_cache_get(redis_client, node="entry_router", input_payload={"a": 1}) is None


@pytest.mark.asyncio
async def test_classify_entry_phase_cached_hits(
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    from app.forge.skills.catalog import catalog_skill_bundle_hash

    first = await classify_entry_phase_cached(
        redis_client, "把背景改成紫色", has_prior_version=True
    )
    assert first == EntryPhase.CODE
    # 第二次应命中缓存；篡改 Redis 后仍返回缓存值可证明走了 cache
    payload = {"requirement": "把背景改成紫色", "has_prior_version": True}
    key = build_exact_cache_key(
        node="entry_router",
        input_payload=payload,
        skill_bundle_hash=catalog_skill_bundle_hash(),
    )
    await redis_client.set(key, '"plan"')
    second = await classify_entry_phase_cached(
        redis_client, "把背景改成紫色", has_prior_version=True
    )
    assert second == EntryPhase.PLAN


@pytest.mark.asyncio
async def test_skill_bundle_hash_change_misses_cache(
    redis_client: fakeredis.aioredis.FakeRedis, monkeypatch: pytest.MonkeyPatch
) -> None:
    await classify_entry_phase_cached(redis_client, "把背景改成紫色", has_prior_version=True)
    monkeypatch.setattr("app.forge.cache.routers.catalog_skill_bundle_hash", lambda: "changed-hash")
    # hash 变了应重新计算，不会读到旧 key
    payload = {"requirement": "把背景改成紫色", "has_prior_version": True}
    assert (
        await exact_cache_get(
            redis_client,
            node="entry_router",
            input_payload=payload,
            skill_bundle_hash="changed-hash",
        )
        is None
    )
    again = await classify_entry_phase_cached(
        redis_client, "把背景改成紫色", has_prior_version=True
    )
    assert again == EntryPhase.CODE


@pytest.mark.asyncio
async def test_normalize_engine_id_cached(
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    assert await normalize_engine_id_cached(redis_client, "phaser3") == "phaser3"
    assert await normalize_engine_id_cached(redis_client, "unknown") == "canvas"
    keys = await redis_client.keys("forge:exact:engine_router:*")
    assert len(keys) >= 1


@pytest.mark.asyncio
async def test_get_template_cached(redis_client: fakeredis.aioredis.FakeRedis) -> None:
    from app.forge.templates.loader import list_templates

    rows = list_templates()
    assert rows, "catalog 应有至少一条模板"
    tid = str(rows[0]["template_id"])
    a = await get_template_cached(redis_client, tid)
    b = await get_template_cached(redis_client, tid)
    assert a["template_id"] == tid
    assert b == a
    keys = await redis_client.keys("forge:exact:template_selection:*")
    assert len(keys) >= 1
