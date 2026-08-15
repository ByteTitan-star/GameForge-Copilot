"""本地沙箱后端：temp workspace + 可选 subprocess 构建。

注意：M5 本地后端**无容器隔离**，仅适合同步生成链联调；真实容器隔离/seccomp/无网络在 M6
DockerSandbox 落地。不要把它当生产沙箱。
"""

import asyncio
import tempfile
from collections.abc import Sequence
from pathlib import Path

from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult
from app.sandbox.collect import collect_artifact_files

_TIMEOUT_S = 60


class LocalSandbox:
    async def execute(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        with tempfile.TemporaryDirectory() as ws:
            workspace = Path(ws)
            for rel, content in source.items():
                p = workspace / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                # 显式 UTF-8：LLM 产物以 str 传入，Windows 默认 CP936(GBK)
                # 会让含中文的 HTML 以 GBK 落盘，后续 qa_node 的
                # read_text(encoding="utf-8") 直接 UnicodeDecodeError。
                p.write_text(content, encoding="utf-8")
            logs = "source passthrough"
            if build_cmd is not None:
                run_logs, error = await self._run_build(workspace, list(build_cmd))
                logs = run_logs
                if error is not None:
                    SANDBOX_RUNS.labels("local", "fail").inc()
                    return BuildResult(ok=False, logs=logs, error=error)
            try:
                files = collect_artifact_files(workspace, collect_root=collect_root)
            except Exception as e:  # noqa: BLE001
                SANDBOX_RUNS.labels("local", "fail").inc()
                return BuildResult(ok=False, logs=logs, error=str(e))
            if "index.html" not in files:
                SANDBOX_RUNS.labels("local", "fail").inc()
                return BuildResult(ok=False, logs=logs, error="产物缺少 index.html")
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
