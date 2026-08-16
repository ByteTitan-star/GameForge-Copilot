"""P3.3：sandbox tier 推荐（telemetry 启发式；默认不自动调度）。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.sandbox.base import OneShotSandboxAdapter
from app.sandbox.local import LocalSandbox
from app.sandbox.tiers import (
    TierSignals,
    clear_tier_telemetry_for_tests,
    recommend_tier,
    record_sandbox_outcome,
)


@pytest.fixture(autouse=True)
def _reset_tier_state(monkeypatch: pytest.MonkeyPatch):
    clear_tier_telemetry_for_tests()
    monkeypatch.setattr(settings, "sandbox_default_tier", "standard")
    monkeypatch.setattr(settings, "sandbox_tier_auto", False)
    yield
    clear_tier_telemetry_for_tests()


def test_recommend_defaults_to_configured_tier() -> None:
    assert recommend_tier(TierSignals()) == "standard"


def test_recommend_upgrades_on_oom_or_timeout_history() -> None:
    record_sandbox_outcome(tier="standard", ok=False, error="OOM killed")
    record_sandbox_outcome(tier="standard", ok=False, error="构建超时")
    assert recommend_tier(TierSignals()) == "heavy"


def test_recommend_heavy_for_large_source_or_vite_hint() -> None:
    big = {"a.js": "x" * 600_000}
    assert recommend_tier(TierSignals(source=big)) == "heavy"
    assert recommend_tier(TierSignals(hints={"engine_id": "vite"})) == "heavy"


def test_recommend_lite_only_when_small_and_safe() -> None:
    small = {"index.html": "<html></html>"}
    assert (
        recommend_tier(TierSignals(source=small, hints={"engine_id": "canvas"}))
        == "lite"
    )
    # 有失败历史时不降档
    record_sandbox_outcome(tier="standard", ok=False, error="timeout")
    assert (
        recommend_tier(TierSignals(source=small, hints={"engine_id": "canvas"}))
        == "heavy"
    )


@pytest.mark.asyncio
async def test_flag_off_oneshot_uses_backend_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sandbox_tier_auto", False)
    seen: list[str | None] = []

    class Spy(LocalSandbox):
        async def create(self, *, tier: str | None = None):
            seen.append(tier)
            return await super().create(tier=tier)

    adapter = OneShotSandboxAdapter(Spy())
    await adapter.execute(source={"index.html": "<html></html>"})
    assert seen == [None]


@pytest.mark.asyncio
async def test_flag_on_oneshot_passes_recommended_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sandbox_tier_auto", True)
    seen: list[str | None] = []

    class Spy(LocalSandbox):
        async def create(self, *, tier: str | None = None):
            seen.append(tier)
            return await super().create(tier=tier)

    adapter = OneShotSandboxAdapter(Spy())
    await adapter.execute(
        source={"index.html": "<html></html>"},
        hints={"engine_id": "canvas"},
    )
    assert seen == ["lite"]
