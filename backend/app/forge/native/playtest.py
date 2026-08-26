"""Native Engine playtest 适配（ADR-13 → CodeQaLoop 桥接）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.forge.native.engine_spec import EngineFamily, get_engine_spec
from app.forge.native.godot.diagnostics import (
    NativeStructuredDiagnostic,
    structured_from_loop_result,
)
from app.forge.native.godot.pipeline import run_godot_p0_loop


@dataclass(frozen=True)
class NativePlaytestResult:
    ok: bool
    errors: list[str]
    console_logs: list[str]
    failure_kind: str | None
    playtest_mode: str
    structured: NativeStructuredDiagnostic | None = None


def should_run_native_playtest(engine_id: str, artifact_dir: Path) -> bool:
    spec = get_engine_spec(engine_id)
    if spec is None or spec.family is not EngineFamily.NATIVE:
        return False
    return (artifact_dir / "project.godot").is_file()


async def run_native_playtest(engine_id: str, artifact_dir: Path) -> NativePlaytestResult:
    if engine_id == "godot4":
        loop = await run_godot_p0_loop(artifact_dir)
        structured = structured_from_loop_result(loop)
        if loop.ok:
            return NativePlaytestResult(
                ok=True,
                errors=[],
                console_logs=[structured.stderr_excerpt] if structured.stderr_excerpt else [],
                failure_kind=None,
                playtest_mode="godot_native",
                structured=structured,
            )
        errors = list(loop.diagnostics.messages) or [structured.summary]
        logs = loop.diagnostics.logs_excerpt.splitlines() if loop.diagnostics.logs_excerpt else []
        kind = "build" if loop.phase in ("validate", "build") else "product"
        return NativePlaytestResult(
            ok=False,
            errors=errors,
            console_logs=logs[:20],
            failure_kind=kind,
            playtest_mode="godot_native",
            structured=structured,
        )
    return NativePlaytestResult(
        ok=False,
        errors=[f"unsupported native engine: {engine_id}"],
        console_logs=[],
        failure_kind="build",
        playtest_mode="native",
        structured=None,
    )
