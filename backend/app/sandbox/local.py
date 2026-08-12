"""本地沙箱后端：temp workspace + 可选 subprocess 构建。

注意：M5 本地后端**无容器隔离**，仅适合同步生成链联调；真实容器隔离/seccomp/无网络在 M6
DockerSandbox 落地。不要把它当生产沙箱。
"""

import asyncio
import tempfile
from collections.abc import Sequence
from pathlib import Path

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult

_TIMEOUT_S = 60


class LocalSandbox:
    async def execute(
        self, source: dict[str, str], build_cmd: Sequence[str] | None = None
    ) -> BuildResult:
        with tempfile.TemporaryDirectory() as ws:
            workspace = Path(ws)
            for rel, content in source.items():
                p = workspace / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            if build_cmd is not None:
                logs, error = await self._run_build(workspace, list(build_cmd))
                if error is not None:
                    SANDBOX_RUNS.labels("local", "fail").inc()
                    return BuildResult(ok=False, logs=logs, error=error)
            files = self._collect(workspace)
            if "index.html" not in files:
                SANDBOX_RUNS.labels("local", "fail").inc()
                return BuildResult(ok=False, logs="", error="产物缺少 index.html")
            logs = "build ok" if build_cmd else "source passthrough"
            SANDBOX_RUNS.labels("local", "ok").inc()
            return BuildResult(ok=True, files=files, logs=logs)

    async def _run_build(self, workspace: Path, build_cmd: list[str]) -> tuple[str, str | None]:
        try:
            proc = await asyncio.create_subprocess_exec(
                *build_cmd,
                cwd=workspace,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            return "", str(e)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_TIMEOUT_S)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return "", "构建超时"
        logs = (stdout or b"").decode(errors="replace") + (stderr or b"").decode(errors="replace")
        if proc.returncode != 0:
            return logs, f"构建退出码 {proc.returncode}"
        return logs, None

    def _collect(self, workspace: Path) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        total = 0
        limit = settings.artifact_max_size_mb * 1024 * 1024
        for p in workspace.rglob("*"):
            if not p.is_file():
                continue
            data = p.read_bytes()
            total += len(data)
            if total > limit:
                raise AppError(ErrorCode.QUOTA_EXCEEDED, "产物超出大小上限")
            files[str(p.relative_to(workspace))] = data
        return files
