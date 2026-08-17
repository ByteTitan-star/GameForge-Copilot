"""dev 启动自动 seed 官方游戏（lifespan）的回归测试。

httpx.ASGITransport 不触发 lifespan，故这里手动驱动 lifespan 验证 seed 分支。
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import settings
from app.games.official import SeedResult
from app.main import lifespan


async def test_lifespan_seeds_official_games_in_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    async def _spy(_session: Any) -> SeedResult:
        calls.append(_session)
        return SeedResult(created=0, refreshed=0)

    monkeypatch.setattr("app.main.seed_official_games", _spy)
    monkeypatch.setattr(settings, "env", "development")

    async with lifespan(None):  # type: ignore[arg-type]
        pass

    assert len(calls) == 1


async def test_lifespan_skips_seed_outside_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Any] = []

    async def _spy(_session: Any) -> SeedResult:
        calls.append(_session)
        return SeedResult(created=0, refreshed=0)

    monkeypatch.setattr("app.main.seed_official_games", _spy)
    monkeypatch.setattr(settings, "env", "production")
    # production 启动会校验 JWT；测 seed 跳过分支时需给合法 secret
    monkeypatch.setattr(
        settings,
        "jwt_secret",
        "ci-test-jwt-secret-at-least-32-chars!!",
    )

    async with lifespan(None):  # type: ignore[arg-type]
        pass

    assert calls == []
