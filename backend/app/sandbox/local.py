"""本地沙箱后端：temp workspace + 可选 subprocess 构建。

注意：本地后端**无容器隔离**，仅适合同步生成链联调；真实容器隔离在 DockerSandbox。
不要把它当生产沙箱。
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult, SandboxSession
from app.sandbox.collect import collect_artifact_files
from app.sandbox.paths import resolve_workspace_rel
from app.sandbox.procutil import run_local_process
from app.sandbox.resources import tier_limits


class LocalSandbox:
    """P3 SandboxBackend：create / execute(session) / destroy。"""

    backend_id = "local"

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        """创建本地临时工作区目录。

        场景：开发联调或无 Docker 环境 fallback。
        参数：tier - 资源档位（影响超时）。
        返回：handle 为目录路径的 SandboxSession。
        """
        workspace = Path(tempfile.mkdtemp(prefix="gf-local-sandbox-"))
        return SandboxSession.new(self.backend_id, tier=tier or "standard", handle=str(workspace))

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        """在会话工作区内写入源码、可选构建并采集产物。

        场景：LocalSandbox 主执行路径（无容器隔离）。
        参数：session、source、build_cmd、collect_root。
        返回：BuildResult。
        """
        if session.closed or not session.handle:
            return BuildResult(ok=False, error="sandbox session closed")
        workspace = Path(session.handle)
        return await self._execute_in_workspace(
            workspace,
            source,
            build_cmd,
            collect_root=collect_root,
            tier=session.tier,
        )

    async def destroy(self, session: SandboxSession) -> None:
        """删除本地工作区并关闭会话。

        场景：oneshot 结束或 HITL 销毁。
        参数：session - 待清理会话。
        """
        if session.closed:
            return
        if session.handle:
            shutil.rmtree(session.handle, ignore_errors=True)
        session.closed = True
        session.handle = None

    async def execute_oneshot(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        """一次性执行：create → execute → destroy（兼容旧测试）。"""
        session = await self.create()
        try:
            return await self.execute(session, source, build_cmd, collect_root=collect_root)
        finally:
            await self.destroy(session)

    async def _execute_in_workspace(
        self,
        workspace: Path,
        source: dict[str, str],
        build_cmd: Sequence[str] | None,
        *,
        collect_root: str,
        tier: str | None = None,
    ) -> BuildResult:
        """在指定工作区执行写入、构建与产物采集（内部复用）。

        场景：execute 与 execute_oneshot 共用逻辑。
        参数：workspace、source、build_cmd、collect_root、tier。
        返回：BuildResult。
        """
        for rel, content in source.items():
            p = resolve_workspace_rel(workspace, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            # 显式 UTF-8：LLM 产物以 str 传入，Windows 默认 CP936(GBK)
            # 会让含中文的 HTML 以 GBK 落盘，后续 qa_node 的
            # read_text(encoding="utf-8") 直接 UnicodeDecodeError。
            p.write_text(content, encoding="utf-8")
        logs = "source passthrough"
        if build_cmd is not None:
            run_logs, error = await self._run_build(workspace, list(build_cmd), tier=tier)
            logs = run_logs
            if error is not None:
                SANDBOX_RUNS.labels("local", "fail").inc()
                kind: Literal["timeout", "build"] = "timeout" if error == "构建超时" else "build"
                return BuildResult(ok=False, logs=logs, error=error, failure_kind=kind)
        try:
            files = collect_artifact_files(workspace, collect_root=collect_root)
        except Exception as e:  # noqa: BLE001
            SANDBOX_RUNS.labels("local", "fail").inc()
            return BuildResult(ok=False, logs=logs, error=str(e), failure_kind="build")
        if "index.html" not in files:
            SANDBOX_RUNS.labels("local", "fail").inc()
            return BuildResult(
                ok=False, logs=logs, error="产物缺少 index.html", failure_kind="build"
            )
        SANDBOX_RUNS.labels("local", "ok").inc()
        return BuildResult(ok=True, files=files, logs=logs)

    async def _run_build(
        self,
        workspace: Path,
        build_cmd: list[str],
        *,
        tier: str | None = None,
    ) -> tuple[str, str | None]:
        """在本地子进程执行构建命令并处理超时。

        场景：_execute_in_workspace 有 build_cmd 时。
        参数：workspace、build_cmd、tier（决定 timeout）。
        返回：(日志文本, 错误文案或 None)。
        """
        timeout = float(tier_limits(tier)["timeout_s"])
        try:
            code, logs = await run_local_process(build_cmd, cwd=workspace, timeout_s=timeout)
        except FileNotFoundError as e:
            return "", str(e)
        if code == -1 and logs == "构建超时":
            return "", "构建超时"
        if code != 0:
            return logs, f"构建退出码 {code}"
        return logs, None
