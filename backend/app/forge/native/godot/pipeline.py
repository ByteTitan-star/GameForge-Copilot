"""Native Engine P0 闭环编排（Validate → Build → Run）。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from app.forge.native.godot.adapter import GodotAdapter, GodotDiagnostics
from app.forge.native.godot.factory import create_godot_adapter
from app.forge.native.metrics import record_native_loop, record_native_phase

DEFAULT_ENGINE = "godot4"


@dataclass(frozen=True)
class NativeLoopResult:
    ok: bool
    phase: str
    diagnostics: GodotDiagnostics


async def _run_phase(
    engine: str,
    phase: str,
    coro,
) -> GodotDiagnostics:
    started = time.perf_counter()
    result: GodotDiagnostics = await coro
    record_native_phase(
        engine,
        phase,
        ok=result.ok,
        duration_s=time.perf_counter() - started,
        error_type=result.error_code,
    )
    return result


async def run_godot_p0_loop(
    workspace: Path,
    *,
    adapter: GodotAdapter | None = None,
    engine: str = DEFAULT_ENGINE,
) -> NativeLoopResult:
    loop_started = time.perf_counter()
    adapter = adapter or create_godot_adapter()
    validate = await _run_phase(engine, "validate", adapter.validate_project(workspace))
    if not validate.ok:
        record_native_loop(engine, ok=False, total_s=time.perf_counter() - loop_started)
        return NativeLoopResult(ok=False, phase="validate", diagnostics=validate)
    build = await _run_phase(engine, "build", adapter.build(workspace))
    if not build.ok:
        record_native_loop(engine, ok=False, total_s=time.perf_counter() - loop_started)
        return NativeLoopResult(ok=False, phase="build", diagnostics=build)
    run = await _run_phase(engine, "run", adapter.run_headless(workspace))
    record_native_loop(engine, ok=run.ok, total_s=time.perf_counter() - loop_started)
    if not run.ok:
        return NativeLoopResult(ok=False, phase="run", diagnostics=run)
    return NativeLoopResult(ok=True, phase="run", diagnostics=run)
