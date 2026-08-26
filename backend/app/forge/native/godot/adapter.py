"""Godot 4.x P0 适配器（ADR-13）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.forge.native.godot.runner import GodotProcessResult, GodotRunner

_MAIN_SCENE_RE = re.compile(r'run/main_scene="(?P<path>[^"]+)"')
_LOG_TAIL = 4000


@dataclass(frozen=True)
class GodotDiagnostics:
    phase: str
    ok: bool
    messages: tuple[str, ...]
    error_code: str | None = None
    logs_excerpt: str = ""


class GodotAdapter:
    """固定模板 + 平台钉死 Godot 版本；Agent 仅填 scenes/scripts。"""

    READY_SIGNAL = "GAMEFORGE_READY"

    def __init__(
        self,
        *,
        godot_version: str,
        template_root: Path,
        runner: GodotRunner | None = None,
    ) -> None:
        self.godot_version = godot_version
        self.template_root = template_root
        self._runner = runner

    def _runner_or_settings(self) -> GodotRunner:
        if self._runner is not None:
            return self._runner
        return GodotRunner(
            godot_bin=settings.native_engine_godot_bin,
            docker_image=settings.native_engine_godot_docker_image,
            build_timeout_s=float(settings.native_engine_godot_build_timeout_s),
            run_timeout_s=float(settings.native_engine_godot_run_timeout_s),
            ready_signal=self.READY_SIGNAL,
            log_tail_chars=_LOG_TAIL,
        )

    def template_dir(self) -> Path:
        return self.template_root

    def _main_scene_path(self, workspace: Path) -> Path | None:
        project = workspace / "project.godot"
        if not project.is_file():
            return None
        text = project.read_text(encoding="utf-8")
        match = _MAIN_SCENE_RE.search(text)
        if not match:
            return None
        rel = match.group("path").removeprefix("res://")
        return workspace / Path(rel)

    @staticmethod
    def _from_process(phase: str, result: GodotProcessResult) -> GodotDiagnostics:
        if result.ok:
            return GodotDiagnostics(
                phase=phase,
                ok=True,
                messages=(),
                logs_excerpt=result.logs,
            )
        code = result.error_code or "INTERNAL_ERROR"
        msg = f"{code}: godot exit={result.exit_code}"
        if result.logs.strip():
            msg = f"{msg}; see logs_excerpt"
        return GodotDiagnostics(
            phase=phase,
            ok=False,
            messages=(msg,),
            error_code=code,
            logs_excerpt=result.logs,
        )

    async def validate_project(self, workspace: Path) -> GodotDiagnostics:
        project = workspace / "project.godot"
        if not project.is_file():
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=("VALIDATION_FAILED: missing project.godot",),
                error_code="VALIDATION_FAILED",
            )
        main_scene = self._main_scene_path(workspace)
        if main_scene is None:
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=("VALIDATION_FAILED: run/main_scene not declared",),
                error_code="VALIDATION_FAILED",
            )
        if not main_scene.is_file():
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=(f"VALIDATION_FAILED: main scene missing: {main_scene.name}",),
                error_code="VALIDATION_FAILED",
            )
        return GodotDiagnostics(phase="validate", ok=True, messages=())

    async def build(self, workspace: Path) -> GodotDiagnostics:
        runner = self._runner_or_settings()
        if not runner.configured():
            return GodotDiagnostics(
                phase="build",
                ok=False,
                messages=(
                    "INTERNAL_ERROR: configure NATIVE_ENGINE_GODOT_BIN "
                    "or NATIVE_ENGINE_GODOT_DOCKER_IMAGE",
                ),
                error_code="INTERNAL_ERROR",
            )
        result = await runner.import_project(workspace)
        return self._from_process("build", result)

    async def run_headless(self, workspace: Path) -> GodotDiagnostics:
        runner = self._runner_or_settings()
        if not runner.configured():
            return GodotDiagnostics(
                phase="run",
                ok=False,
                messages=(
                    "INTERNAL_ERROR: configure NATIVE_ENGINE_GODOT_BIN "
                    "or NATIVE_ENGINE_GODOT_DOCKER_IMAGE",
                ),
                error_code="INTERNAL_ERROR",
            )
        result = await runner.run_until_ready(workspace)
        return self._from_process("run", result)
