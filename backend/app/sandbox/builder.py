"""Builder 容器/本地子进程：Dependency Prepare 与 Build Sandbox 共用。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import aiodocker
from aiodocker.exceptions import DockerError

from app.core.config import settings
from app.core.metrics import SANDBOX_RUNS
from app.forge.build.profile import BuildProfile
from app.sandbox.procutil import run_local_process
from app.sandbox.resources import docker_log_host_config, docker_user_spec

_PACKAGE_MANAGER_RE = re.compile(r"^pnpm@\d+(\.\d+)*$")


def sanitize_package_manager_version(package_manager: str) -> str | None:
    """从 packageManager 字段提取白名单内的 pnpm 版本号。

    场景：manifest 校验 ADR-07 packageManager 约束。
    参数：package_manager - 如 pnpm@11.21.0。
    返回：版本字符串或 None（格式不符）。
    """
    pm = (package_manager or "").strip()
    if not _PACKAGE_MANAGER_RE.fullmatch(pm):
        return None
    return pm.split("@", 1)[1]


@dataclass
class BuilderRunResult:
    ok: bool
    logs: str = ""
    error: str | None = None
    files: dict[str, bytes] = field(default_factory=dict)


def resolve_store_path(raw: str | None = None) -> Path:
    """解析并确保 pnpm store 目录存在。

    场景：DockerBuilder/LocalBuilder 初始化 bind mount。
    参数：raw - 可选路径，默认 settings.pnpm_store_path。
    返回：绝对路径 Path。
    """
    path = Path(raw or settings.pnpm_store_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_bind_mount_permissions(path: Path, *, recursive: bool = True) -> None:
    """Docker builder 以宿主 uid 运行；bind mount 需可读写（CI 临时目录权限不一致）。"""
    if os.name == "nt" or not path.exists():
        return
    import stat

    def _chmod(target: Path) -> None:
        """为单个路径补全读写权限（保留可执行位）。

        场景：_ensure_bind_mount_permissions 递归 chmod。
        参数：target — 文件或目录路径。
        返回：无。
        """
        try:
            current = target.stat().st_mode
        except OSError:
            return
        if target.is_dir():
            desired = current | stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO
        else:
            # 保留可执行位（esbuild 等原生二进制依赖 +x）
            desired = (
                current
                | stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IROTH
                | stat.S_IWOTH
            )
            if current & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                desired |= stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
        with contextlib.suppress(OSError):
            os.chmod(target, desired)

    _chmod(path)
    if recursive and path.is_dir():
        for child in path.rglob("*"):
            _chmod(child)


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
        sanitized = sanitize_package_manager_version(str(pm or ""))
        if sanitized:
            version = sanitized
    return f"corepack prepare pnpm@{version} --activate && "


def pnpm_setup_shell(*, store_dir: str = "/pnpm/store", workspace: Path | None = None) -> str:
    """生成 pnpm registry 与 store-dir 配置 shell 片段。

    场景：builder 容器/本地执行 install 前环境准备。
    参数：store_dir - store 挂载路径；workspace - 可选，用于设置 cache-dir。
    返回：可拼入 sh -c 的配置命令串。
    """
    prefix = corepack_activate_shell(workspace) if workspace else ""
    pnpm = pnpm_cli()
    registry = settings.npm_registry
    store = store_dir
    cache_cfg = ""
    if workspace is not None:
        # 目录名勿含 "pnpm" 子串，否则 pin_docker_pnpm 会误替换路径
        cache_path = workspace / ".build-cache"
        if os.name == "nt":
            cache_cfg = f'{pnpm} config set cache-dir "{cache_path}" && '
        else:
            cp = str(cache_path).replace("'", "")
            cache_cfg = f"pnpm config set cache-dir '{cp}' && "
    if os.name == "nt":
        return (
            f"{prefix}"
            f"{cache_cfg}"
            f'{pnpm} config set registry "{registry}" && '
            f'{pnpm} config set store-dir "{store}"'
        )
    reg = registry.replace("'", "")
    st = store.replace("'", "")
    return (
        f"{prefix}{cache_cfg}pnpm config set registry '{reg}' && pnpm config set store-dir '{st}'"
    )


def offline_install_shell(setup: str) -> str:
    """离线安装：prepare 阶段已在线校验 lockfile，此处信任 lockfile 避免无网复检。"""
    pnpm = pnpm_cli()
    return (
        f"{setup} && "
        f"{pnpm} install --offline --frozen-lockfile --frozen-store --trust-lockfile && "
        f"{pnpm} build"
    )


def prepare_install_shell(setup: str) -> str:
    """生成在线 lockfile 校验与 fetch 的 shell 片段。

    场景：Dependency Prepare 阶段（在线环境）。
    参数：setup - pnpm_setup_shell 等前置配置。
    返回：含 install --lockfile-only 与 fetch 的命令串。
    """
    pnpm = pnpm_cli()
    return f"{setup} && {pnpm} install --lockfile-only && {pnpm} fetch"


def shell_cmd(script: str) -> list[str]:
    """Unix 容器用 sh -c；LocalBuilder 在 Windows 会转为 subprocess shell。"""
    return ["sh", "-c", script]


def pin_docker_pnpm(script: str) -> str:
    """Docker 构建使用 /usr/local/bin/pnpm，避免 corepack 在 NetworkMode=none 时联网。"""
    import re

    # 勿替换路径片段（如 /pnpm/store）
    return re.sub(r"(?<![/\w-])pnpm\b", "/usr/local/bin/pnpm", script)


def _shell_script(cmd: Sequence[str]) -> str | None:
    """从 ``sh -c`` 命令列表提取内联脚本正文。

    场景：DockerBuilder/LocalBuilder 判断是否为 shell 模式。
    参数：cmd - 命令 argv 序列。
    返回：脚本字符串，非 sh -c 形式时返回 None。
    """
    parts = list(cmd)
    if len(parts) >= 3 and parts[0] == "sh" and parts[1] == "-c":
        return parts[2]
    return None


class DockerBuilder:
    """在 gameforge-builder 镜像中执行 pnpm 命令（§9）。"""

    def __init__(self, image: str | None = None, store_path: str | None = None) -> None:
        """初始化 Docker 构建器。

        参数：image - builder 镜像；store_path - pnpm store 宿主路径。
        """
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
        """在 gameforge-builder 容器中执行构建命令。

        场景：Forge 依赖安装与 Vite build。
        参数：workspace - 工作区；cmd - 命令；network_mode/store_readonly/timeout_s - 容器选项。
        返回：BuilderRunResult（含日志与退出状态）。
        """
        timeout = timeout_s or settings.builder_timeout_s
        _ensure_bind_mount_permissions(workspace.resolve())
        # 勿递归 chmod store 内包文件，否则会剥掉 esbuild 等二进制的 +x
        _ensure_bind_mount_permissions(self.store_path.resolve(), recursive=False)
        store_mode = "ro" if store_readonly else "rw"
        binds = [
            f"{workspace.resolve()}:/workspace:rw",
            f"{self.store_path.resolve()}:/pnpm/store:{store_mode}",
        ]
        cmd_list = list(cmd)
        script = _shell_script(cmd_list)
        if script is not None:
            cmd_list = shell_cmd(pin_docker_pnpm(script))
        config = {
            "Image": self.image,
            "Cmd": cmd_list,
            "WorkingDir": "/workspace",
            "User": docker_user_spec(),
            "Env": [
                "HOME=/tmp",
                "PATH=/usr/local/bin:/pnpm:/usr/bin:/bin",
                f"npm_config_registry={settings.npm_registry}",
            ],
            "HostConfig": {
                "Binds": binds,
                "NetworkMode": network_mode,
                "Memory": 1024 * 1024 * 1024,
                "NanoCpus": 2_000_000_000,
                "ReadonlyRootfs": True,
                "Tmpfs": {"/tmp": "rw,noexec,nosuid,size=512m"},  # nosec B108
                "SecurityOpt": ["no-new-privileges:true"],
                "CapDrop": ["ALL"],
                **docker_log_host_config(),
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
                name=f"gf-builder-{workspace.name}",
                config=config,  # type: ignore[arg-type]
            )
            await container.start()
            try:
                wait_result = await asyncio.wait_for(container.wait(), timeout=timeout)
            except TimeoutError:
                await container.kill()
                SANDBOX_RUNS.labels("builder", "timeout").inc()
                return BuilderRunResult(ok=False, error="构建超时")
            logs = await container.log(stdout=True, stderr=True, tail=settings.sandbox_log_tail)
            log_text = "".join(logs) if isinstance(logs, list) else str(logs)
            code = wait_result.get("StatusCode", 1) if isinstance(wait_result, dict) else 1
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
        """初始化本地 pnpm 构建器（无容器隔离）。

        参数：store_path - pnpm store 路径。
        """
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
        """在宿主进程执行 pnpm 构建（开发 fallback）。

        场景：settings.builder_backend != docker 时。
        参数：workspace、cmd、timeout_s 等同 DockerBuilder.run。
        返回：BuilderRunResult。
        """
        timeout = timeout_s or settings.builder_timeout_s
        env = os.environ.copy()
        env["npm_config_registry"] = settings.npm_registry
        script = _shell_script(cmd)
        try:
            if script is not None and os.name == "nt":
                code, logs = await run_local_process(
                    [],
                    cwd=workspace,
                    env=env,
                    timeout_s=timeout,
                    shell=True,  # nosec B604 — Windows local builder only; script from controlled cmd
                    shell_script=script,
                )
            else:
                code, logs = await run_local_process(cmd, cwd=workspace, env=env, timeout_s=timeout)
        except FileNotFoundError as e:
            return BuilderRunResult(ok=False, error=str(e))
        if code == -1 and logs == "构建超时":
            return BuilderRunResult(ok=False, error="构建超时")
        if code != 0:
            return BuilderRunResult(ok=False, logs=logs, error=f"构建退出码 {code}")
        return BuilderRunResult(ok=True, logs=logs or "builder ok")


def get_builder() -> DockerBuilder | LocalBuilder:
    """按 settings.builder_backend 返回 Docker 或本地 Builder 实例。

    场景：Forge build 入口选择构建后端。
    返回：DockerBuilder 或 LocalBuilder。
    """
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
    """将 BuildProfile 序列化写入工作区 build-profile.json。

    场景：构建前落盘 toolchain/catalog 版本供审计与缓存 key。
    参数：workspace - 目标目录；profile - 构建配置。
    """
    (workspace / "build-profile.json").write_text(profile.to_json(), encoding="utf-8")
