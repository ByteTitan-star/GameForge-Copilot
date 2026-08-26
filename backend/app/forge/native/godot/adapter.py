"""Godot 4.x P0 适配器骨架（ADR-13；Validate/Build/Run 待 P0 PoC 实现）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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

    async def validate_project(self, workspace: Path) -> GodotDiagnostics:
        project = workspace / "project.godot"
        if not project.is_file():
            return GodotDiagnostics(
                phase="validate",
                ok=False,
                messages=("STRUCTURAL: missing project.godot",),
            )
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
