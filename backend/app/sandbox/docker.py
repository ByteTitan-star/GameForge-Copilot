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

import aiodocker
from aiodocker.exceptions import DockerError

from app.core.config import settings
from app.core.errors import AppError
from app.core.metrics import SANDBOX_RUNS
from app.sandbox.base import BuildResult, SandboxSession
from app.sandbox.collect import collect_artifact_files

_TIERS: dict[str, dict] = {
    "standard": {"mem_limit": "512m", "nano_cpus": 1_000_000_000, "timeout_s": 60},
    "heavy": {"mem_limit": "1g", "nano_cpus": 2_000_000_000, "timeout_s": 120},
}


class DockerSandbox:
    """按 session 准备工作区；execute 时拉起 sandbox 镜像，network=none，用完可 destroy。"""

    backend_id = "docker"

    def __init__(self, image: str | None = None, tier: str | None = None) -> None:
        self.image = image or settings.sandbox_image
        self.default_tier = tier or settings.sandbox_default_tier

    async def create(self, *, tier: str | None = None) -> SandboxSession:
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
        if session.closed or not session.handle:
            return BuildResult(ok=False, error="sandbox session closed")
        limits = _TIERS.get(session.tier, _TIERS["standard"])
        workspace = Path(session.handle)
        for rel, content in source.items():
            p = workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        try:
            result = await self._run_container(workspace, build_cmd, limits, collect_root)
            SANDBOX_RUNS.labels("docker", "ok" if result.ok else "fail").inc()
            return result
        except DockerError as e:
            SANDBOX_RUNS.labels("docker", "error").inc()
            return BuildResult(ok=False, error=f"docker error: {e}")
        except Exception as e:  # noqa: BLE001
            SANDBOX_RUNS.labels("docker", "error").inc()
            return BuildResult(ok=False, error=str(e))

    async def destroy(self, session: SandboxSession) -> None:
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
        session = await self.create(tier=tier)
        try:
            return await self.execute(
                session, source, build_cmd, collect_root=collect_root
            )
        finally:
            await self.destroy(session)

    async def _run_container(
        self,
        workspace: Path,
        build_cmd: Sequence[str] | None,
        limits: dict,
        collect_root: str = ".",
    ) -> BuildResult:
        cmd = list(build_cmd) if build_cmd else ["sh", "-c", "test -f /workspace/index.html"]
        config = {
            "Image": self.image,
            "Cmd": cmd,
            "WorkingDir": "/workspace",
            "HostConfig": {
                "Binds": [f"{workspace.resolve()}:/workspace:rw"],
                "NetworkMode": "none",
                "Memory": _parse_mem(limits["mem_limit"]),
                "NanoCpus": limits["nano_cpus"],
                "ReadonlyRootfs": True,
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=64m"},
                "SecurityOpt": ["no-new-privileges:true"],
                "CapDrop": ["ALL"],
            },
        }
        docker = aiodocker.Docker()
        container = None
        try:
            try:
                await docker.images.inspect(self.image)
            except DockerError:
                await docker.images.pull(self.image)
            container = await docker.containers.create_or_replace(
                name=f"gf-sandbox-{workspace.name}", config=config
            )
            await container.start()
            try:
                await asyncio.wait_for(container.wait(), timeout=limits["timeout_s"])
            except TimeoutError:
                await container.kill()
                return BuildResult(ok=False, error="构建超时")
            logs = await container.log(stdout=True, stderr=True)
            log_text = "".join(logs) if isinstance(logs, list) else str(logs)
            info = await container.show()
            code = (info.get("State") or {}).get("ExitCode", 1)
            if code != 0:
                return BuildResult(ok=False, logs=log_text, error=f"构建退出码 {code}")
            try:
                files = collect_artifact_files(workspace, collect_root=collect_root)
            except AppError as e:
                return BuildResult(ok=False, logs=log_text, error=e.message)
            if "index.html" not in files:
                return BuildResult(ok=False, logs=log_text, error="产物缺少 index.html")
            return BuildResult(ok=True, files=files, logs=log_text or "build ok")
        finally:
            if container is not None:
                with contextlib.suppress(DockerError):
                    await container.delete(force=True)
            await docker.close()


def _parse_mem(spec: str) -> int:
    s = spec.strip().lower()
    if s.endswith("g"):
        return int(float(s[:-1]) * 1024**3)
    if s.endswith("m"):
        return int(float(s[:-1]) * 1024**2)
    return int(s)
