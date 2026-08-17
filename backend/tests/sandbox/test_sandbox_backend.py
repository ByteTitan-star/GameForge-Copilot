"""P3：SandboxBackend create/execute/destroy 生命周期。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.sandbox import get_sandbox, get_sandbox_backend, reset_sandbox_for_tests
from app.sandbox.base import SandboxBackend, SandboxSession
from app.sandbox.daytona import DaytonaSandbox
from app.sandbox.local import LocalSandbox


@pytest.mark.asyncio
async def test_local_backend_lifecycle_create_execute_destroy() -> None:
    backend: SandboxBackend = LocalSandbox()
    session = await backend.create(tier="standard")
    assert isinstance(session, SandboxSession)
    assert session.backend_id == "local"
    result = await backend.execute(
        session,
        source={"index.html": "<!DOCTYPE html><html><body>ok</body></html>"},
    )
    assert result.ok
    assert "index.html" in result.files
    await backend.destroy(session)
    assert session.closed


@pytest.mark.asyncio
async def test_oneshot_execute_still_works_via_get_sandbox() -> None:
    reset_sandbox_for_tests()
    settings.sandbox_backend = "local"
    sb = get_sandbox()
    result = await sb.execute({"index.html": "<!DOCTYPE html><html><body>x</body></html>"})
    assert result.ok
    reset_sandbox_for_tests()


@pytest.mark.asyncio
async def test_daytona_blocked_when_disabled() -> None:
    settings.sandbox_daytona_enabled = False
    settings.daytona_api_key = "dtn_test"
    backend = DaytonaSandbox()
    with pytest.raises(AppError) as ei:
        await backend.create()
    assert "disabled" in ei.value.message.lower() or "ADR-03" in ei.value.message
    settings.sandbox_daytona_enabled = True


def test_factory_rejects_unknown_backend() -> None:
    reset_sandbox_for_tests()
    settings.sandbox_backend = "not-a-backend"
    with pytest.raises(AppError):
        get_sandbox_backend()
    reset_sandbox_for_tests()
    settings.sandbox_backend = "local"


def test_factory_daytona_falls_back_when_disabled() -> None:
    """sandbox_backend=daytona 但未启用时回退 docker→local（ADR-03）。"""
    reset_sandbox_for_tests()
    settings.sandbox_backend = "daytona"
    settings.sandbox_daytona_enabled = False
    backend = get_sandbox_backend()
    assert not isinstance(backend, DaytonaSandbox)
    assert backend.backend_id in {"docker", "local"}
    reset_sandbox_for_tests()
    settings.sandbox_backend = "local"
    settings.sandbox_daytona_enabled = True
