"""Native Engine P0 闭环编排（Validate → Build → Run）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.forge.native.godot.adapter import GodotDiagnostics
from app.forge.native.godot.factory import create_godot_adapter


@dataclass(frozen=True)
class NativeLoopResult:
    ok: bool
    phase: str
    diagnostics: GodotDiagnostics


async def run_godot_p0_loop(workspace: Path) -> NativeLoopResult:
    adapter = create_godot_adapter()
    validate = await adapter.validate_project(workspace)
    if not validate.ok:
        return NativeLoopResult(ok=False, phase="validate", diagnostics=validate)
    build = await adapter.build(workspace)
    if not build.ok:
        return NativeLoopResult(ok=False, phase="build", diagnostics=build)
    run = await adapter.run_headless(workspace)
    if not run.ok:
        return NativeLoopResult(ok=False, phase="run", diagnostics=run)
    return NativeLoopResult(ok=True, phase="run", diagnostics=run)
