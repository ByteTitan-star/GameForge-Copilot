"""Godot runner unit tests (mocked subprocess)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.forge.native.godot.runner import GodotRunner


class _FakeStdout:
    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines
        self._idx = 0

    async def readline(self) -> bytes:
        if self._idx >= len(self._lines):
            return b""
        line = self._lines[self._idx]
        self._idx += 1
        return line


class _FakeProc:
    def __init__(self, lines: list[bytes]) -> None:
        self.stdout = _FakeStdout(lines)
        self.returncode: int | None = None
        self.pid = 4242

    async def wait(self) -> int:
        return int(self.returncode or 0)


@pytest.mark.asyncio
async def test_run_until_ready_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProc([b"loading\n", b"GAMEFORGE_READY\n"])

    async def _fake_exec(*_args, **_kwargs) -> _FakeProc:
        return fake

    killed: list[bool] = []

    async def _fake_kill(proc: _FakeProc) -> None:
        _ = proc
        killed.append(True)
        fake.returncode = 0

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr("app.forge.native.godot.runner._kill_process", _fake_kill)

    runner = GodotRunner(
        godot_bin="godot",
        build_timeout_s=10,
        run_timeout_s=5,
    )
    result = await runner.run_until_ready(Path("/tmp/project"))
    assert result.ok is True
    assert result.ready_seen is True
    assert "GAMEFORGE_READY" in result.logs
    assert killed


@pytest.mark.asyncio
async def test_run_until_ready_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeProc([b"loading forever\n"])

    async def _slow_readline() -> bytes:
        await asyncio.sleep(10)
        return b""

    fake.stdout.readline = _slow_readline  # type: ignore[method-assign]

    async def _fake_exec(*_args, **_kwargs) -> _FakeProc:
        return fake

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
    monkeypatch.setattr("app.forge.native.godot.runner._kill_process", lambda _p: asyncio.sleep(0))

    runner = GodotRunner(
        godot_bin="godot",
        build_timeout_s=10,
        run_timeout_s=0.2,
    )
    result = await runner.run_until_ready(Path("/tmp/project"))
    assert result.ok is False
    assert result.error_code == "READY_TIMEOUT"


@pytest.mark.asyncio
async def test_import_project_delegates_to_run_local_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    async def _fake_run(*_cmd, **_kwargs) -> tuple[int, str]:
        return 0, "import ok"

    monkeypatch.setattr("app.forge.native.godot.runner.run_local_process", _fake_run)
    runner = GodotRunner(godot_bin="godot", build_timeout_s=10, run_timeout_s=5)
    result = await runner.import_project(tmp_path)
    assert result.ok is True
    assert "import ok" in result.logs


def test_runner_configured_with_docker_image_only() -> None:
    runner = GodotRunner(
        godot_bin="",
        docker_image="gameforge-godot-builder:v1",
        build_timeout_s=10,
        run_timeout_s=5,
    )
    assert runner.configured() is True


@pytest.mark.asyncio
async def test_import_project_uses_docker_cmd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: list[list[str]] = []

    async def _fake_run(cmd, **_kwargs) -> tuple[int, str]:
        captured.append(list(cmd))
        return 0, "docker import ok"

    monkeypatch.setattr("app.forge.native.godot.runner.run_local_process", _fake_run)
    runner = GodotRunner(
        godot_bin="",
        docker_image="gameforge-godot-builder:v1",
        build_timeout_s=10,
        run_timeout_s=5,
    )
    result = await runner.import_project(tmp_path)
    assert result.ok is True
    assert captured
    assert captured[0][0:3] == ["docker", "run", "--rm"]
