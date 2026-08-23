"""Dependency Prepare：在线 lockfile 生成 + store 填充（硬约束①，§9.2）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.forge.build.profile import BuildProfile
from app.sandbox.builder import (
    BuilderRunResult,
    DockerBuilder,
    LocalBuilder,
    get_builder,
    pnpm_setup_shell,
    prepare_cache_key,
    prepare_install_shell,
    shell_cmd,
    write_build_profile,
)


@dataclass
class PrepareResult:
    ok: bool
    logs: str = ""
    error: str | None = None
    skipped: bool = False
    cache_key: str = ""


class DependencyPreparer:
    """同步幂等依赖准备；未来可替换为 worker 队列（§14）。"""

    def __init__(self, builder: DockerBuilder | LocalBuilder | None = None) -> None:
        """初始化依赖准备器。

        场景：BuildPipeline 默认 preparer。
        参数：builder - 可选沙箱构建后端。
        返回：无。
        """
        self._builder = builder or get_builder()

    def _setup_shell(self, workspace: Path) -> str:
        """生成 pnpm store 初始化 shell 片段。

        场景：prepare / offline build 共用。
        参数：workspace - 项目根目录。
        返回：shell 脚本字符串。
        """
        store = "/pnpm/store"
        if isinstance(self._builder, LocalBuilder):
            store = str(self._builder.store_path.resolve())
        return pnpm_setup_shell(store_dir=store, workspace=workspace)

    async def prepare(self, workspace: Path, profile: BuildProfile) -> PrepareResult:
        """在线生成 lockfile 并填充 pnpm store（可缓存跳过）。

        场景：Vite 流水线第一步。
        参数：workspace、profile。
        返回：PrepareResult（ok/skipped/logs）。
        """
        cache_key = prepare_cache_key(workspace, profile)
        lockfile = workspace / "pnpm-lock.yaml"
        marker = workspace / ".prepare-cache-key"
        cached = marker.is_file() and marker.read_text(encoding="utf-8") == cache_key
        if lockfile.is_file() and cached:
            return PrepareResult(
                ok=True,
                skipped=True,
                cache_key=cache_key,
                logs="prepare cache hit",
            )

        write_build_profile(workspace, profile)
        shell = prepare_install_shell(self._setup_shell(workspace))
        result = await self._run(workspace, shell, online=True)
        if not result.ok:
            return PrepareResult(
                ok=False,
                logs=result.logs,
                error=result.error,
                cache_key=cache_key,
            )

        marker.write_text(cache_key, encoding="utf-8")
        return PrepareResult(ok=True, logs=result.logs, cache_key=cache_key)

    async def _run(self, workspace: Path, shell: str, *, online: bool) -> BuilderRunResult:
        """在沙箱 builder 中执行 shell（在线或离线网络模式）。

        场景：prepare 与 offline build 内部调用。
        参数：workspace、shell、online - 是否允许联网。
        返回：BuilderRunResult。
        """
        network = "bridge" if online else "none"
        return await self._builder.run(
            workspace,
            shell_cmd(shell),
            network_mode=network,
            store_readonly=not online,
        )
