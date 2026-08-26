"""Godot 4.x P0 适配器（ADR-13）。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_MAIN_SCENE_RE = re.compile(r'run/main_scene="(?P<path>[^"]+)"')


@dataclass(frozen=True)
class GodotDiagnostics:
    phase: str
    ok: bool
    messages: tuple[str, ...]


class GodotAdapter:
    """固定模板 + 平台钉死 Godot 版本；Agent 仅填 scenes/scripts。"""

    READY_SIGNAL = "GAMEFORGE_READY"

    def __init__(self, *, godot_version: str, template_root: Path) -> None:
        self.godot_version = godot_version
        self.template_root = template_root

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

    async def validate_project(self, workspace: Path) -> GodotDiagnostics:
        project = workspace / "project.godot"
        if not project.is_file():
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=("STRUCTURAL: missing project.godot",),
            )
        main_scene = self._main_scene_path(workspace)
        if main_scene is None:
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=("STRUCTURAL: run/main_scene not declared in project.godot",),
            )
        if not main_scene.is_file():
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=(f"STRUCTURAL: main scene missing: {main_scene.name}",),
            )
        bootstrap = workspace / "gameforge" / "bootstrap.gd"
        if bootstrap.is_file():
            return GodotDiagnostics(phase="validate", ok=True, messages=())
        # bootstrap 目录可选于最小模板；main scene 存在即通过 P0 validate
        return GodotDiagnostics(phase="validate", ok=True, messages=())

    async def build(self, workspace: Path) -> GodotDiagnostics:
        _ = workspace
        return GodotDiagnostics(
            phase="build",
            ok=False,
            messages=("NOT_IMPLEMENTED: Godot build pipeline (ADR-13 P0)",),
        )

    async def run_headless(self, workspace: Path) -> GodotDiagnostics:
        _ = workspace
        return GodotDiagnostics(
            phase="run",
            ok=False,
            messages=("NOT_IMPLEMENTED: Godot headless run (ADR-13 P0)",),
        )
