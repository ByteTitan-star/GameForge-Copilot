"""Builder 容器/本地子进程：Dependency Prepare 与 Build Sandbox 共用。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import aiodocker
from aiodocker.exceptions import DockerError

from app.core.config import settings
from app.core.metrics import SANDBOX_RUNS
from app.forge.build.profile import BuildProfile


@dataclass
class BuilderRunResult:
    ok: bool
    logs: str = ""
    error: str | None = None
    files: dict[str, bytes] = field(default_factory=dict)


def resolve_store_path(raw: str | None = None) -> Path:
    path = Path(raw or settings.pnpm_store_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def pnpm_cli() -> str:
    """Docker/Linux 直接用 pnpm；Windows 本地 fallback 须走 corepack 避免全局旧版 pnpm。"""
    return "corepack pnpm" if os.name == "nt" else "pnpm"


def corepack_activate_shell(workspace: Path) -> str:
    """Windows 本地：按 package.json#packageManager 激活 pnpm 版本。"""
    if os.name != "nt":
        return ""
    version = "11.21.0"
    pkg_path = workspace / "package.json"
    if pkg_path.is_file():
        pm = json.loads(pkg_path.read_text(encoding="utf-8")).get("packageManager", "")
        if pm.startswith("pnpm@"):
            version = pm.split("@", 1)[1]
    return f"corepack prepare pnpm@{version} --activate && "


def pnpm_setup_shell(*, store_dir: str = "/pnpm/store", workspace: Path | None = None) -> str:
    prefix = corepack_activate_shell(workspace) if workspace else ""
    pnpm = pnpm_cli()
    registry = settings.npm_registry
    store = store_dir
    if os.name == "nt":
        return (
            f"{prefix}"
            f'{pnpm} config set registry "{registry}" && '
            f'{pnpm} config set store-dir "{store}"'
        )
    reg = registry.replace("'", "")
    st = store.replace("'", "")
    return f"{prefix}pnpm config set registry '{reg}' && pnpm config set store-dir '{st}'"


def offline_install_shell(setup: str) -> str:
    pnpm = pnpm_cli()
    return (
        f"{setup} && "
        f"{pnpm} install --offline --frozen-lockfile --frozen-store && "
        f"{pnpm} build"
    )


def prepare_install_shell(setup: str) -> str:
    pnpm = pnpm_cli()
    return f"{setup} && {pnpm} install --lockfile-only && {pnpm} fetch"


def shell_cmd(script: str) -> list[str]:
    """Unix 容器用 sh -c；LocalBuilder 在 Windows 会转为 subprocess shell。"""
    return ["sh", "-c", script]


def _shell_script(cmd: Sequence[str]) -> str | None:
    parts = list(cmd)
    if len(parts) >= 3 and parts[0] == "sh" and parts[1] == "-c":
        return parts[2]
    return None


class DockerBuilder:
    """在 gameforge-builder 镜像中执行 pnpm 命令（§9）。"""

    def __init__(self, image: str | None = None, store_path: str | None = None) -> None:
        self.image = image or settings.builder_image
        self.store_path = resolve_store_path(store_path)

    async def run(
        self,
        workspace: Path,
        cmd: Sequence[str],
        *,
        network_mode: str = "none",
        store_readonly: bool = True,
        timeout_s: int | None = None,
    ) -> BuilderRunResult:
        timeout = timeout_s or settings.builder_timeout_s
        store_mode = "ro" if store_readonly else "rw"
        binds = [
            f"{workspace.resolve()}:/workspace:rw",
            f"{self.store_path.resolve()}:/pnpm/store:{store_mode}",
        ]
        config = {
            "Image": self.image,
            "Cmd": list(cmd),
            "WorkingDir": "/workspace",
            "HostConfig": {
                "Binds": binds,
                "NetworkMode": network_mode,
                "Memory": 1024 * 1024 * 1024,
                "NanoCpus": 2_000_000_000,
                "ReadonlyRootfs": True,
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=128m"},
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
                name=f"gf-builder-{workspace.name}", config=config
            )
            await container.start()
            try:
                await asyncio.wait_for(container.wait(), timeout=timeout)
            except TimeoutError:
                await container.kill()
                SANDBOX_RUNS.labels("builder", "timeout").inc()
                return BuilderRunResult(ok=False, error="构建超时")
            logs = await container.log(stdout=True, stderr=True)
            log_text = "".join(logs) if isinstance(logs, list) else str(logs)
            info = await container.show()
            code = (info.get("State") or {}).get("ExitCode", 1)
            if code != 0:
                SANDBOX_RUNS.labels("builder", "fail").inc()
                return BuilderRunResult(ok=False, logs=log_text, error=f"构建退出码 {code}")
            SANDBOX_RUNS.labels("builder", "ok").inc()
            return BuilderRunResult(ok=True, logs=log_text or "builder ok")
        except DockerError as e:
            SANDBOX_RUNS.labels("builder", "error").inc()
            return BuilderRunResult(ok=False, error=f"docker error: {e}")
        finally:
            if container is not None:
                with contextlib.suppress(DockerError):
                    await container.delete(force=True)
            await docker.close()


class LocalBuilder:
    """本地 pnpm 构建（§24 开发 fallback，无容器隔离）。"""

    def __init__(self, store_path: str | None = None) -> None:
        self.store_path = resolve_store_path(store_path)

    async def run(
        self,
        workspace: Path,
        cmd: Sequence[str],
        *,
        network_mode: str = "none",  # noqa: ARG002
        store_readonly: bool = True,  # noqa: ARG002
        timeout_s: int | None = None,
    ) -> BuilderRunResult:
        timeout = timeout_s or settings.builder_timeout_s
        env = os.environ.copy()
        env["npm_config_registry"] = settings.npm_registry
        script = _shell_script(cmd)
        try:
            if script is not None and os.name == "nt":
                proc = await asyncio.create_subprocess_shell(
                    script,
                    cwd=workspace,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    cwd=workspace,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                )
        except FileNotFoundError as e:
            return BuilderRunResult(ok=False, error=str(e))
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return BuilderRunResult(ok=False, error="构建超时")
        logs = (stdout or b"").decode(errors="replace") + (stderr or b"").decode(errors="replace")
        if proc.returncode != 0:
            return BuilderRunResult(ok=False, logs=logs, error=f"构建退出码 {proc.returncode}")
        return BuilderRunResult(ok=True, logs=logs or "builder ok")


def get_builder() -> DockerBuilder | LocalBuilder:
    if settings.builder_backend == "docker":
        return DockerBuilder()
    return LocalBuilder()


def prepare_cache_key(workspace: Path, profile: BuildProfile) -> str:
    """幂等 cache key：toolchain + catalog + manifest + platform（§14）。"""
    parts = [
        profile.builder_version,
        profile.dependency_catalog_version,
        profile.template_version,
    ]
    for name in ("package.json", "pnpm-workspace.yaml"):
        p = workspace / name
        if p.is_file():
            parts.append(p.read_text(encoding="utf-8"))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def write_build_profile(workspace: Path, profile: BuildProfile) -> None:
    (workspace / "build-profile.json").write_text(profile.to_json(), encoding="utf-8")
