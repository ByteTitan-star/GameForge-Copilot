"""本地子进程：POSIX 进程组；Windows 退化为 proc.kill（ADR-11）。"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
from collections.abc import Sequence


async def run_local_process(
    cmd: Sequence[str],
    *,
    cwd: str | os.PathLike[str],
    env: dict[str, str] | None = None,
    timeout_s: float,
    shell: bool = False,
    shell_script: str | None = None,
) -> tuple[int, str]:
    """启动子进程并等待；超时则杀进程组（POSIX）或 kill（Windows）。"""
    kwargs: dict = {
        "cwd": cwd,
        "stdout": asyncio.subprocess.PIPE,
        "stderr": asyncio.subprocess.PIPE,
        "env": env,
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True
    if shell and shell_script is not None:
        proc = await asyncio.create_subprocess_shell(shell_script, **kwargs)
    else:
        proc = await asyncio.create_subprocess_exec(*cmd, **kwargs)
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        await _kill_process_tree(proc)
        await proc.wait()
        return -1, "构建超时"
    logs = (stdout or b"").decode(errors="replace") + (stderr or b"").decode(errors="replace")
    return int(proc.returncode or 0), logs


async def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """终止子进程；POSIX 杀整组，Windows 退化为 proc.kill。

    场景：run_local_process 超时时清理残留子进程。
    参数：proc - 已启动的 asyncio 子进程。
    """
    if proc.returncode is not None:
        return
    if os.name != "nt" and proc.pid:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[attr-defined]
            return
    with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
        proc.kill()
