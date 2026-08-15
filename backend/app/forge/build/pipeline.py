"""P1 构建编排：固定 Vite+TS 模板 → prepare → offline build → dist/。"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.forge.build.constants import BUILD_SNAPSHOT_FILES
from app.forge.build.dependency_preparer import DependencyPreparer, PrepareResult
from app.forge.build.profile import BuildProfile, default_build_profile
from app.forge.build.template import load_vite_ts_template_files
from app.sandbox.builder import (
    BuilderRunResult,
    DockerBuilder,
    LocalBuilder,
    get_builder,
    offline_install_shell,
    pnpm_setup_shell,
    shell_cmd,
)
from app.sandbox.collect import collect_artifact_files


@dataclass
class BuildPipelineResult:
    ok: bool
    dist: dict[str, bytes] = field(default_factory=dict)
    build_snapshot: dict[str, bytes] = field(default_factory=dict)
    prepare: PrepareResult | None = None
    logs: str = ""
    error: str | None = None


def _collect_build_snapshot(workspace: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for name in BUILD_SNAPSHOT_FILES:
        path = workspace / name
        if path.is_file():
            out[name] = path.read_bytes()
    return out


def _write_workspace(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class BuildPipeline:
    """P1 固定模板构建链；P2 起接入 LLM project 输出。"""

    def __init__(
        self,
        preparer: DependencyPreparer | None = None,
        builder: DockerBuilder | LocalBuilder | None = None,
    ) -> None:
        self._preparer = preparer or DependencyPreparer()
        self._builder = builder or get_builder()

    async def run_vite_ts_demo(self, profile: BuildProfile | None = None) -> BuildPipelineResult:
        prof = profile or default_build_profile()
        with tempfile.TemporaryDirectory() as ws:
            workspace = Path(ws)
            _write_workspace(workspace, load_vite_ts_template_files())
            prep = await self._preparer.prepare(workspace, prof)
            if not prep.ok:
                return BuildPipelineResult(ok=False, prepare=prep, logs=prep.logs, error=prep.error)

            build = await self._offline_build(workspace)
            if not build.ok:
                return BuildPipelineResult(
                    ok=False,
                    prepare=prep,
                    logs=prep.logs + "\n" + build.logs,
                    error=build.error,
                )
            try:
                dist = collect_artifact_files(workspace, collect_root="dist")
            except Exception as e:  # noqa: BLE001
                return BuildPipelineResult(
                    ok=False,
                    prepare=prep,
                    logs=build.logs,
                    error=str(e),
                )
            if "index.html" not in dist:
                return BuildPipelineResult(
                    ok=False,
                    prepare=prep,
                    logs=build.logs,
                    error="dist 缺少 index.html",
                )
            return BuildPipelineResult(
                ok=True,
                dist=dist,
                build_snapshot=_collect_build_snapshot(workspace),
                prepare=prep,
                logs=prep.logs + "\n" + build.logs,
            )

    async def _offline_build(self, workspace: Path) -> BuilderRunResult:
        store = "/pnpm/store"
        if isinstance(self._builder, LocalBuilder):
            store = str(self._builder.store_path.resolve())
        setup = pnpm_setup_shell(store_dir=store, workspace=workspace)
        shell = offline_install_shell(setup)
        return await self._builder.run(
            workspace,
            shell_cmd(shell),
            network_mode="none",
            store_readonly=True,
        )
