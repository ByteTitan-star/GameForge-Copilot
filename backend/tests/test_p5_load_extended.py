"""扩展 Load（opt-in marker）：高于 smoke 的并发，仍非生产长时 soak。"""

from __future__ import annotations

import asyncio
import os

import fakeredis.aioredis
import pytest

from app.core.config import settings
from app.forge.cache.exact import exact_cache_get, exact_cache_set
from app.forge.skills.router import resolve_skills_for_node
from app.sandbox.tiers import (
    TierSignals,
    clear_tier_telemetry_for_tests,
    recommend_tier,
    record_sandbox_outcome,
)

_LOAD_N = int(os.environ.get("LOAD_CONCURRENCY", "120"))


pytestmark = pytest.mark.load


@pytest.mark.asyncio
async def test_load_exact_cache_whitelist_high_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "exact_cache_enabled", True)
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def one(i: int) -> None:
        payload = {"k": i}
        assert await exact_cache_set(
            r, node="template_selection", input_payload=payload, value={"i": i}
        )
        got = await exact_cache_get(r, node="template_selection", input_payload=payload)
        assert got == {"i": i}

    await asyncio.gather(*(one(i) for i in range(_LOAD_N)))


@pytest.mark.asyncio
async def test_load_skill_router_and_tier_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_tier_telemetry_for_tests()
    monkeypatch.setattr(settings, "sandbox_default_tier", "standard")

    async def route(i: int) -> str:
        resolved = await asyncio.to_thread(
            resolve_skills_for_node,
            "code",
            hints={"engine_id": "phaser3" if i % 2 else "canvas"},
        )
        return resolved.methodology[0].id

    async def spray(i: int) -> None:
        await asyncio.to_thread(
            lambda: record_sandbox_outcome(
                tier="standard",
                ok=False,
                error="timeout" if i % 7 == 0 else None,
            )
        )

    ids = await asyncio.gather(*(route(i) for i in range(_LOAD_N)))
    await asyncio.gather(*(spray(i) for i in range(_LOAD_N)))
    assert "code/phaser3" in ids and "code/canvas" in ids
    assert recommend_tier(TierSignals()) == "heavy"
    clear_tier_telemetry_for_tests()
