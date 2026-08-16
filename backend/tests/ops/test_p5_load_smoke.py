"""P5 Load smoke：进程内并发压力（非全量压测 / 非 k6）。

覆盖 Exact Cache 白名单 roundtrip、Skill 路由、tier telemetry 记录在 gather 下的正确性。
全量 Load / Chaos 实验窗仍 gated。
"""

from __future__ import annotations

import asyncio

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


@pytest.mark.asyncio
async def test_exact_cache_whitelist_concurrent_roundtrip_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "exact_cache_enabled", True)
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)

    async def one(i: int) -> None:
        payload = {"prompt": f"engine-{i}", "n": i}
        value = {"ok": True, "i": i}
        assert await exact_cache_set(r, node="engine_router", input_payload=payload, value=value)
        got = await exact_cache_get(r, node="engine_router", input_payload=payload)
        assert got == value

    await asyncio.gather(*(one(i) for i in range(48)))
    assert (
        await exact_cache_get(r, node="engine_router", input_payload={"prompt": "engine-0", "n": 0})
    )["i"] == 0
    assert (
        await exact_cache_get(
            r, node="engine_router", input_payload={"prompt": "engine-47", "n": 47}
        )
    )["i"] == 47


@pytest.mark.asyncio
async def test_skill_router_concurrent_resolves_stable() -> None:
    async def one(i: int) -> list[str]:
        resolved = await asyncio.to_thread(
            resolve_skills_for_node,
            "art" if i % 2 == 0 else "code",
            hints=(
                {"style": "像素风"}
                if i % 2 == 0
                else {"engine_id": "phaser3" if i % 4 == 1 else "canvas"}
            ),
        )
        return [s.id for s in resolved.methodology]

    results = await asyncio.gather(*(one(i) for i in range(40)))
    for i, ids in enumerate(results):
        assert ids
        if i % 2 == 0:
            assert "art/pixel-art" in ids
            assert all(not x.startswith(("billing/", "code/")) for x in ids)
        else:
            expect = "code/phaser3" if i % 4 == 1 else "code/canvas"
            assert ids[0] == expect


@pytest.mark.asyncio
async def test_tier_telemetry_concurrent_record_and_upgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_tier_telemetry_for_tests()
    monkeypatch.setattr(settings, "sandbox_default_tier", "standard")

    async def spray(i: int) -> None:
        def _record() -> None:
            record_sandbox_outcome(
                tier="standard",
                ok=i % 5 != 0,
                error="OOM killed" if i % 5 == 0 else None,
            )

        await asyncio.to_thread(_record)

    await asyncio.gather(*(spray(i) for i in range(24)))
    record_sandbox_outcome(tier="standard", ok=False, error="构建超时")
    assert recommend_tier(TierSignals()) == "heavy"
    clear_tier_telemetry_for_tests()
