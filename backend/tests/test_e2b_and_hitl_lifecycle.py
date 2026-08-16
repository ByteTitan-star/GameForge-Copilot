"""E2B SDK 适配（mock）与 HITL destroy/restore 编排。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.sandbox.e2b import E2BSandbox, clear_e2b_live_for_tests
from app.sandbox.lifecycle import destroy_for_hitl, restore_after_hitl
from app.sandbox.local import LocalSandbox


class _FakeFiles:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def write(self, path: str, data: str) -> None:
        self.store[path] = data

    async def read(self, path: str, format: str = "text") -> Any:
        text = self.store.get(path, "")
        return text.encode("utf-8") if format == "bytes" else text


class _FakeCommands:
    def __init__(self, files: _FakeFiles) -> None:
        self.files = files

    async def run(self, cmd: str, timeout: float = 60) -> SimpleNamespace:
        if cmd.startswith("mkdir"):
            return SimpleNamespace(stdout="", stderr="", exit_code=0)
        if cmd.startswith("find "):
            root = cmd.split(" ", 1)[1].split(" ", 1)[0]
            paths = [p for p in self.files.store if p.startswith(root)]
            return SimpleNamespace(stdout="\n".join(paths), stderr="", exit_code=0)
        if "&&" in cmd and "false" in cmd:
            return SimpleNamespace(stdout="", stderr="boom", exit_code=1)
        return SimpleNamespace(stdout="ok", stderr="", exit_code=0)


class _FakeSandbox:
    def __init__(self) -> None:
        self.sandbox_id = "sbx_test_1"
        self.files = _FakeFiles()
        self.commands = _FakeCommands(self.files)
        self.killed = False

    async def kill(self) -> None:
        self.killed = True


@pytest.fixture(autouse=True)
def _reset_e2b() -> None:
    clear_e2b_live_for_tests()
    yield
    clear_e2b_live_for_tests()


@pytest.mark.asyncio
async def test_e2b_create_blocked_when_disabled() -> None:
    settings.sandbox_e2b_enabled = False
    with pytest.raises(AppError):
        await E2BSandbox().create()


@pytest.mark.asyncio
async def test_e2b_lifecycle_with_mocked_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    settings.sandbox_e2b_enabled = True
    fake = _FakeSandbox()

    class _AS:
        @staticmethod
        async def create(**_kwargs: Any) -> _FakeSandbox:
            return fake

    monkeypatch.setattr("app.sandbox.e2b._import_async_sandbox", lambda: _AS)
    backend = E2BSandbox()
    session = await backend.create(tier="standard")
    assert session.backend_id == "e2b"
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
    assert fake.killed is True
    settings.sandbox_e2b_enabled = False


@pytest.mark.asyncio
async def test_hitl_destroy_and_restore_local() -> None:
    backend = LocalSandbox()
    session = await backend.create()
    meta = await destroy_for_hitl(backend, session)
    assert meta["destroyed_for_hitl"] is True
    assert session.closed
    restored = await restore_after_hitl(backend, tier="standard")
    assert not restored.closed
    assert restored.id != session.id
    await backend.destroy(restored)
