"""Native structured diagnostics tests."""

from __future__ import annotations

from app.forge.native.godot.adapter import GodotDiagnostics
from app.forge.native.godot.diagnostics import (
    build_native_repair_context,
    structured_from_diagnostics,
    structured_from_loop_result,
)
from app.forge.native.godot.pipeline import NativeLoopResult


def test_structured_from_build_failure() -> None:
    diag = GodotDiagnostics(
        phase="build",
        ok=False,
        messages=("BUILD_FAILED: godot exit=1",),
        error_code="BUILD_FAILED",
        logs_excerpt="Error: script parse failed",
    )
    out = structured_from_diagnostics(diag, engine_version="4.3")
    assert out.error_type == "BUILD_FAILED"
    assert out.retryable is True
    assert out.engine_version == "4.3"
    assert "parse failed" in out.stderr_excerpt


def test_repair_context_includes_json_block() -> None:
    diag = GodotDiagnostics(
        phase="run",
        ok=False,
        messages=("READY_TIMEOUT",),
        error_code="READY_TIMEOUT",
        logs_excerpt="loading...",
    )
    structured = structured_from_diagnostics(diag)
    ctx = build_native_repair_context(structured, repair_history=["attempt 1 failed"])
    assert "Native Engine Structured Diagnostic" in ctx
    assert "READY_TIMEOUT" in ctx
    assert "attempt 1 failed" in ctx


def test_loop_success_structured() -> None:
    result = NativeLoopResult(
        ok=True,
        phase="run",
        diagnostics=GodotDiagnostics(
            phase="run", ok=True, messages=(), logs_excerpt="GAMEFORGE_READY"
        ),
    )
    out = structured_from_loop_result(result)
    assert out.error_type == "OK"
    assert out.retryable is False
