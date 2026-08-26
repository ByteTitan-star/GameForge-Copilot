"""Native Engine metrics tests."""

from __future__ import annotations

from app.core.metrics import (
    NATIVE_ENGINE_LOOP_TOTAL,
    NATIVE_ENGINE_PHASE_TOTAL,
)
from app.forge.native.metrics import record_native_loop, record_native_phase


def test_record_native_phase_increments_ok_counter() -> None:
    before = NATIVE_ENGINE_PHASE_TOTAL.labels("godot4", "validate", "ok")._value.get()
    record_native_phase("godot4", "validate", ok=True, duration_s=0.05)
    after = NATIVE_ENGINE_PHASE_TOTAL.labels("godot4", "validate", "ok")._value.get()
    assert after == before + 1


def test_record_native_phase_increments_fail_and_error() -> None:
    phase_before = NATIVE_ENGINE_PHASE_TOTAL.labels("godot4", "build", "fail")._value.get()
    record_native_phase(
        "godot4",
        "build",
        ok=False,
        duration_s=1.0,
        error_type="BUILD_FAILED",
    )
    phase_after = NATIVE_ENGINE_PHASE_TOTAL.labels("godot4", "build", "fail")._value.get()
    assert phase_after == phase_before + 1


def test_record_native_loop_increments_counter() -> None:
    before = NATIVE_ENGINE_LOOP_TOTAL.labels("godot4", "ok")._value.get()
    record_native_loop("godot4", ok=True, total_s=2.5)
    after = NATIVE_ENGINE_LOOP_TOTAL.labels("godot4", "ok")._value.get()
    assert after == before + 1
