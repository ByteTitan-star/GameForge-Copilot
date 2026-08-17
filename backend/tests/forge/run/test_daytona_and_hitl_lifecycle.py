"""Daytona SDK 适配（mock）与 HITL destroy/restore 编排。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.sandbox.daytona import DaytonaSandbox, clear_daytona_live_for_tests
from app.sandbox.lifecycle import destroy_for_hitl, restore_after_hitl
from app.sandbox.local import LocalSandbox


class _FakeFs:
    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    async def create_folder(self, path: str, mode: str = "755") -> None:
        return None

    async def upload_file(self, data: bytes, path: str) -> None:
        self.store[path] = data

    async def download_file(self, path: str) -> bytes:
        return self.store.get(path, b"")


class _FakeProcess:
    def __init__(self, files: _FakeFs) -> None:
        self.files = files

    async def exec(self, cmd: str, timeout: float = 60) -> SimpleNamespace:
        if cmd.startswith("find "):
            root = cmd.split(" ", 1)[1].split(" ", 1)[0]
            paths = [p for p in self.files.store if p.startswith(root)]
            return SimpleNamespace(result="\n".join(paths), exit_code=0)
        if "&&" in cmd and "false" in cmd:
            return SimpleNamespace(result="boom", exit_code=1)
        return SimpleNamespace(result="ok", exit_code=0)


class _FakeSandbox:
    def __init__(self) -> None:
        self.id = "sbx_test_1"
        self.fs = _FakeFs()
        self.process = _FakeProcess(self.fs)


class _FakeClient:
    def __init__(self, fake: _FakeSandbox) -> None:
        self._fake = fake
        self.deleted = False

    async def create(self, **_kwargs: Any) -> _FakeSandbox:
        return self._fake

    async def get(self, _sandbox_id: str) -> _FakeSandbox:
        return self._fake

    async def delete(self, _sandbox: _FakeSandbox) -> None:
        self.deleted = True


@pytest.fixture(autouse=True)
def _reset_daytona() -> None:
    clear_daytona_live_for_tests()
    yield
    clear_daytona_live_for_tests()


@pytest.mark.asyncio
async def test_daytona_create_blocked_when_disabled() -> None:
    settings.sandbox_daytona_enabled = False
    settings.daytona_api_key = "dtn_test"
    with pytest.raises(AppError):
        await DaytonaSandbox().create()
    settings.sandbox_daytona_enabled = True


@pytest.mark.asyncio
async def test_daytona_lifecycle_with_mocked_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.sandbox_daytona_enabled = True
    settings.daytona_api_key = "dtn_test"
    fake = _FakeSandbox()
    client = _FakeClient(fake)

    monkeypatch.setattr(
        DaytonaSandbox,
        "_new_client",
        lambda self: client,
    )
    backend = DaytonaSandbox()
    session = await backend.create(tier="standard")
    assert session.backend_id == "daytona"
    assert session.handle == "sbx_test_1"
    result = await backend.execute(
        session,
        source={"index.html": "<!DOCTYPE html><html></html>"},
        build_cmd=None,
    )
    assert result.ok
    assert "index.html" in result.files
    await backend.destroy(session)
    assert session.closed
    assert client.deleted is True


@pytest.mark.asyncio
async def test_hitl_destroy_and_restore_local() -> None:
    backend = LocalSandbox()
    session = await backend.create(tier="heavy")
    meta = await destroy_for_hitl(backend, session)
    assert meta["destroyed_for_hitl"] is True
    assert meta["tier"] == "heavy"
    assert session.closed
    from app.sandbox.lifecycle import tier_from_hitl_meta

    restored = await restore_after_hitl(backend, tier=tier_from_hitl_meta(meta))
    assert not restored.closed
    assert restored.tier == "heavy"
    assert restored.id != session.id
    await backend.destroy(restored)


def test_tier_from_hitl_meta_reads_tier() -> None:
    from app.sandbox.lifecycle import tier_from_hitl_meta

    assert tier_from_hitl_meta({"tier": "lite"}) == "lite"
    assert tier_from_hitl_meta({}) is None
    assert tier_from_hitl_meta(None) is None


@pytest.mark.asyncio
async def test_restore_sandbox_from_checkpoint_uses_hitl_tier() -> None:
    from app.sandbox.lifecycle import destroy_for_hitl, restore_sandbox_from_checkpoint

    backend = LocalSandbox()
    session = await backend.create(tier="heavy")
    meta = await destroy_for_hitl(backend, session)
    restored = await restore_sandbox_from_checkpoint(backend, {"sandbox_hitl": meta})
    assert restored is not None
    assert restored.tier == "heavy"
    assert restored.id != session.id
    await backend.destroy(restored)
    assert await restore_sandbox_from_checkpoint(backend, {}) is None
