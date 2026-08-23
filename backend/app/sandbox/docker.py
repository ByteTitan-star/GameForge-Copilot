"""Docker 沙箱：aiodocker 拉起一次性容器（无网络 / 资源分级 / 用完销毁）。

docs/09 §沙箱运维；生产默认。Docker 不可用时调用方应回退 LocalSandbox。
P3：实现 create / execute(session) / destroy；HITL 长等待应 destroy，不保留长会话。
"""

from __future__ import annotations

import asyncio
import contextlib
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import aiodocker
from aiodocker.exceptions import DockerError

from app.core.config import settings
from app.core.errors import AppError
from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult, SandboxSession
from app.sandbox.collect import collect_artifact_files
from app.sandbox.paths import resolve_workspace_rel
from app.sandbox.resources import (
    docker_log_host_config,
    docker_user_spec,
    parse_mem_bytes,
    tier_limits,
)


class DockerSandbox:
    """按 session 准备工作区；execute 时拉起 sandbox 镜像，network=none，用完可 destroy。"""

    backend_id = "docker"

    def __init__(self, image: str | None = None, tier: str | None = None) -> None:
        """配置沙箱镜像与默认资源档位。

        场景：DockerSandbox 实例化。
        参数：image - 容器镜像；tier - 默认 lite/standard/heavy。
        """
        self.image = image or settings.sandbox_image
        self.default_tier = tier or settings.sandbox_default_tier

    async def create(self, *, tier: str | None = None) -> SandboxSession:
        """创建临时工作区目录并返回沙箱会话。

        场景：execute 前准备工作区 bind mount。
        参数：tier - 资源档位。
        返回：handle 为工作区路径的 SandboxSession。
        """
        workspace = Path(tempfile.mkdtemp(prefix="gf-docker-sandbox-"))
        return SandboxSession.new(
            self.backend_id,
            tier=tier or self.default_tier,
            handle=str(workspace),
        )

    async def execute(
        self,
        session: SandboxSession,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult:
        """写入源码并在隔离容器中执行构建、采集产物。

        场景：Forge Code QA 生产沙箱路径。
        参数：session、source、build_cmd、collect_root。
        返回：BuildResult。
        """
        if session.closed or not session.handle:
            return BuildResult(ok=False, error="sandbox session closed", failure_kind="infra")
        limits = tier_limits(session.tier)
        workspace = Path(session.handle)
        try:
            for rel, content in source.items():
                p = resolve_workspace_rel(workspace, rel)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content, encoding="utf-8")
            result = await self._run_container(workspace, build_cmd, limits, collect_root)
            SANDBOX_RUNS.labels("docker", "ok" if result.ok else "fail").inc()
            return result
        except AppError as e:
            SANDBOX_RUNS.labels("docker", "error").inc()
            return BuildResult(ok=False, error=e.message, failure_kind="infra")
        except DockerError as e:
            SANDBOX_RUNS.labels("docker", "error").inc()
            return BuildResult(ok=False, error=f"docker error: {e}", failure_kind="infra")
        except Exception as e:  # noqa: BLE001
            SANDBOX_RUNS.labels("docker", "error").inc()
            return BuildResult(ok=False, error=str(e), failure_kind="infra")

    async def destroy(self, session: SandboxSession) -> None:
        """删除工作区目录并标记会话已关闭。

        场景：构建结束或 HITL 暂停销毁。
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
        tier: str | None = None,
    ) -> BuildResult:
        """一次性 create → execute → destroy（兼容旧调用方）。

        场景：无需长会话的 oneshot 构建。
        参数：source、build_cmd、collect_root、tier。
        返回：BuildResult。
        """
        from app.sandbox.tiers import record_sandbox_outcome, resolve_create_tier

        chosen = resolve_create_tier(source=source, explicit=tier)
        session = await self.create(tier=chosen)
        try:
            result = await self.execute(session, source, build_cmd, collect_root=collect_root)
            record_sandbox_outcome(
                tier=session.tier,
                ok=result.ok,
                error=result.error,
                backend=self.backend_id,
            )
            return result
        finally:
            await self.destroy(session)

    async def _run_container(
        self,
        workspace: Path,
        build_cmd: Sequence[str] | None,
        limits: dict,
        collect_root: str = ".",
    ) -> BuildResult:
        """拉起无网络 Docker 容器执行命令并采集 workspace 产物。

        场景：DockerSandbox.execute 内部。
        参数：workspace、build_cmd、limits、tier 限制、collect_root。
        返回：BuildResult（含超时/OOM/构建错误分类）。
        """
        cmd = list(build_cmd) if build_cmd else ["sh", "-c", "test -f /workspace/index.html"]
        host_config = {
            "Binds": [f"{workspace.resolve()}:/workspace:rw"],
            "NetworkMode": "none",
            "Memory": parse_mem_bytes(limits["mem_limit"]),
            "NanoCpus": limits["nano_cpus"],
            "ReadonlyRootfs": True,
            "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=64m"},  # nosec B108
            "SecurityOpt": ["no-new-privileges:true"],
            "CapDrop": ["ALL"],
            **docker_log_host_config(),
        }
        config = {
            "Image": self.image,
            "Cmd": cmd,
            "WorkingDir": "/workspace",
            "User": docker_user_spec(),
            "HostConfig": host_config,
        }
        docker = aiodocker.Docker()
        container = None
        try:
            try:
                await docker.images.inspect(self.image)
            except DockerError:
                await docker.images.pull(self.image)
            container = await docker.containers.create_or_replace(
                name=f"gf-sandbox-{workspace.name}",
                config=config,  # type: ignore[arg-type]
            )
            await container.start()
            try:
                wait_result = await asyncio.wait_for(container.wait(), timeout=limits["timeout_s"])
            except TimeoutError:
                with contextlib.suppress(DockerError):
                    await container.kill()
                return BuildResult(ok=False, error="构建超时", failure_kind="timeout")
            logs = await container.log(stdout=True, stderr=True, tail=settings.sandbox_log_tail)
            log_text = "".join(logs) if isinstance(logs, list) else str(logs)
            code = wait_result.get("StatusCode", 1) if isinstance(wait_result, dict) else 1
            if code != 0:
                kind: Literal["oom", "build"] = "oom" if _looks_like_oom(log_text) else "build"
                return BuildResult(
                    ok=False, logs=log_text, error=f"构建退出码 {code}", failure_kind=kind
                )
            try:
                files = collect_artifact_files(workspace, collect_root=collect_root)
            except AppError as e:
                return BuildResult(ok=False, logs=log_text, error=e.message, failure_kind="build")
            if "index.html" not in files:
                return BuildResult(
                    ok=False,
                    logs=log_text,
                    error="产物缺少 index.html",
                    failure_kind="build",
                )
            return BuildResult(ok=True, files=files, logs=log_text or "build ok")
        finally:
            if container is not None:
                with contextlib.suppress(DockerError):
                    await container.delete(force=True)
            await docker.close()


def _looks_like_oom(logs: str) -> bool:
    """根据容器日志启发式判断是否为 OOM 杀进程。

    场景：_run_container 构建失败时区分 failure_kind。
    参数：logs - 容器 stdout/stderr 合并文本。
    返回：疑似 OOM 时为 True。
    """
    low = logs.lower()
    return "out of memory" in low or "oom" in low
