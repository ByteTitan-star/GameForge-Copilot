"""P3：SandboxBackend create/execute/destroy 生命周期。"""

from __future__ import annotations

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.sandbox import get_sandbox, get_sandbox_backend, reset_sandbox_for_tests
from app.sandbox.base import SandboxBackend, SandboxSession
from app.sandbox.e2b import E2BSandbox
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
    result = await sb.execute(
        {"index.html": "<!DOCTYPE html><html><body>x</body></html>"}
    )
    assert result.ok
    reset_sandbox_for_tests()


@pytest.mark.asyncio
async def test_e2b_is_poc_only_and_blocked_by_default() -> None:
    settings.sandbox_e2b_enabled = False
    backend = E2BSandbox()
    with pytest.raises(AppError) as ei:
        await backend.create()
    assert "ADR-03" in ei.value.message or "disabled" in ei.value.message.lower()


def test_factory_rejects_unknown_backend() -> None:
    reset_sandbox_for_tests()
    settings.sandbox_backend = "not-a-backend"
    with pytest.raises(AppError):
        get_sandbox_backend()
    reset_sandbox_for_tests()
    settings.sandbox_backend = "local"


def test_factory_accepts_e2b_name_but_create_still_gated() -> None:
    reset_sandbox_for_tests()
    settings.sandbox_backend = "e2b"
    settings.sandbox_e2b_enabled = False
    backend = get_sandbox_backend()
    assert isinstance(backend, E2BSandbox)
    reset_sandbox_for_tests()
    settings.sandbox_backend = "local"
