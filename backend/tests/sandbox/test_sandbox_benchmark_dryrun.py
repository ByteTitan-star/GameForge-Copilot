"""sandbox benchmark dry-run（local）。"""

from __future__ import annotations

import pytest

from app.sandbox.benchmark import run_benchmark


@pytest.mark.asyncio
async def test_sandbox_benchmark_dryrun_local_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DAYTONA_BENCHMARK_LIVE", raising=False)
    report = await run_benchmark(rounds=2)
    assert report["production_default_must_remain"] == "docker"
    assert report["local_dry_run"]["backend"] == "local"
    assert report["local_dry_run"]["rounds"] == 2
    assert report["daytona_live"] is None
