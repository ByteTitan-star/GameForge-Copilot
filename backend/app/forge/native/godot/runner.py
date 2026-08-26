"""Godot CLI 执行与 Ready 协议检测（ADR-13 §3.5）。"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from dataclasses import dataclass
from pathlib import Path

from app.forge.native.godot.docker_exec import build_docker_godot_cmd
from app.sandbox.procutil import run_local_process


@dataclass(frozen=True)
class GodotProcessResult:
    ok: bool
    exit_code: int
    logs: str
    error_code: str | None = None
    ready_seen: bool = False


def _clip_logs(text: str, *, max_chars: int = 4000) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


async def _kill_process(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if os.name != "nt" and proc.pid:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[attr-defined]
            return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        proc.kill()
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(proc.wait(), timeout=5.0)


class GodotRunner:
    """封装 Godot 4 headless 命令；本地 binary 或 Docker 镜像二选一。"""

    def __init__(
        self,
        *,
        godot_bin: str,
        docker_image: str = "",
        build_timeout_s: float,
        run_timeout_s: float,
        ready_signal: str = "GAMEFORGE_READY",
        log_tail_chars: int = 4000,
    ) -> None:
        self.godot_bin = godot_bin.strip()
        self.docker_image = docker_image.strip()
        self.build_timeout_s = build_timeout_s
        self.run_timeout_s = run_timeout_s
        self.ready_signal = ready_signal
        self.log_tail_chars = log_tail_chars

    def configured(self) -> bool:
        return bool(self.godot_bin) or bool(self.docker_image)

    def _godot_args(self, workspace: Path, extra: list[str] | None = None) -> list[str]:
        args = ["--headless", "--path", str(workspace), *(extra or [])]
        if self.docker_image:
            return build_docker_godot_cmd(
                workspace,
                image=self.docker_image,
                godot_args=args,
            )
        return [self.godot_bin, *args]

    async def import_project(self, workspace: Path) -> GodotProcessResult:
        if not self.configured():
            return GodotProcessResult(
                ok=False,
                exit_code=-1,
                logs="",
                error_code="INTERNAL_ERROR",
            )
        code, logs = await run_local_process(
            self._godot_args(workspace, ["--import"]),
            cwd=workspace,
            timeout_s=self.build_timeout_s,
        )
        clipped = _clip_logs(logs, max_chars=self.log_tail_chars)
        if code == 0:
            return GodotProcessResult(ok=True, exit_code=0, logs=clipped)
        return GodotProcessResult(
            ok=False,
            exit_code=code,
            logs=clipped,
            error_code="BUILD_FAILED",
        )

    async def run_until_ready(self, workspace: Path) -> GodotProcessResult:
        if not self.configured():
            return GodotProcessResult(
                ok=False,
                exit_code=-1,
                logs="",
                error_code="INTERNAL_ERROR",
            )
        cmd = self._godot_args(workspace)
        kwargs: dict = {
            "cwd": str(workspace),
            "stdout": asyncio.subprocess.PIPE,
            "stderr": asyncio.subprocess.STDOUT,
        }
        if os.name != "nt":
            kwargs["start_new_session"] = True
        proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
        logs: list[str] = []
        ready = False
        timed_out = False
        if proc.stdout is None:
            await _kill_process(proc)
            return GodotProcessResult(
                ok=False,
                exit_code=-1,
                logs="",
                error_code="RUN_FAILED",
            )
        try:
            async with asyncio.timeout(self.run_timeout_s):
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode(errors="replace")
                    logs.append(text)
                    if self.ready_signal in text:
                        ready = True
                        break
        except TimeoutError:
            timed_out = True
        finally:
            await _kill_process(proc)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(proc.wait(), timeout=5.0)

        clipped = _clip_logs("".join(logs), max_chars=self.log_tail_chars)
        exit_code = int(proc.returncode or 0)
        if ready:
            return GodotProcessResult(
                ok=True,
                exit_code=exit_code,
                logs=clipped,
                ready_seen=True,
            )
        if timed_out:
            return GodotProcessResult(
                ok=False,
                exit_code=exit_code,
                logs=clipped,
                error_code="READY_TIMEOUT",
            )
        return GodotProcessResult(
            ok=False,
            exit_code=exit_code,
            logs=clipped,
            error_code="RUN_FAILED",
        )
