"""Daytona 无 key 时回退 docker/local。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.sandbox import get_sandbox_backend, reset_sandbox_for_tests


@pytest.fixture(autouse=True)
def _reset():
    reset_sandbox_for_tests()
    yield
    reset_sandbox_for_tests()


def test_daytona_backend_falls_back_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sandbox_backend", "daytona")
    monkeypatch.setattr(settings, "sandbox_daytona_enabled", True)
    monkeypatch.setattr(settings, "daytona_api_key", "")
    backend = get_sandbox_backend()
    assert backend.backend_id in {"docker", "local"}
