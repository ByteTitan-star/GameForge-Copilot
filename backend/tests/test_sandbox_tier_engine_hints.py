"""code_qa → sandbox tier hints：从 design_doc 传 engine_id。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.sandbox.base import OneShotSandboxAdapter
from app.sandbox.local import LocalSandbox
from app.sandbox.tiers import clear_tier_telemetry_for_tests, tier_hints_from_design_doc


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch):
    clear_tier_telemetry_for_tests()
    monkeypatch.setattr(settings, "sandbox_tier_auto", True)
    monkeypatch.setattr(settings, "sandbox_default_tier", "standard")
    yield
    clear_tier_telemetry_for_tests()


def test_tier_hints_from_design_doc_reads_engine_id() -> None:
    assert tier_hints_from_design_doc({"engine": {"id": "phaser3"}}) == {
        "engine_id": "phaser3"
    }
    assert tier_hints_from_design_doc({"engine": "canvas"}) == {"engine_id": "canvas"}
    assert tier_hints_from_design_doc({}) == {}
    assert tier_hints_from_design_doc(None) == {}


@pytest.mark.asyncio
async def test_oneshot_uses_design_engine_hint_for_heavy() -> None:
    seen: list[str | None] = []

    class Spy(LocalSandbox):
        async def create(self, *, tier: str | None = None):
            seen.append(tier)
            return await super().create(tier=tier)

    adapter = OneShotSandboxAdapter(Spy())
    hints = tier_hints_from_design_doc({"engine": {"id": "phaser3"}})
    await adapter.execute(source={"index.html": "<html></html>"}, hints=hints)
    assert seen == ["heavy"]
