"""Native Engine Prometheus 埋点（ADR-13 §3.9）。"""

from __future__ import annotations


def record_native_phase(
    engine: str,
    phase: str,
    *,
    ok: bool,
    duration_s: float,
    error_type: str | None = None,
) -> None:
    """记录单阶段结果与耗时；metrics 不可用时不阻断主路径。"""
    try:
        from app.core.metrics import (
            NATIVE_ENGINE_ERRORS,
            NATIVE_ENGINE_PHASE_LATENCY,
            NATIVE_ENGINE_PHASE_TOTAL,
        )

        status = "ok" if ok else "fail"
        NATIVE_ENGINE_PHASE_TOTAL.labels(engine, phase, status).inc()
        NATIVE_ENGINE_PHASE_LATENCY.labels(engine, phase).observe(max(duration_s, 0.0))
        if not ok and error_type:
            NATIVE_ENGINE_ERRORS.labels(engine, phase, error_type).inc()
    except Exception:  # noqa: BLE001 — 与 sandbox tier metrics 同策略
        return


def record_native_loop(engine: str, *, ok: bool, total_s: float) -> None:
    """记录整轮 P0 闭环结果与总耗时。"""
    try:
        from app.core.metrics import NATIVE_ENGINE_LOOP_LATENCY, NATIVE_ENGINE_LOOP_TOTAL

        status = "ok" if ok else "fail"
        NATIVE_ENGINE_LOOP_TOTAL.labels(engine, status).inc()
        NATIVE_ENGINE_LOOP_LATENCY.labels(engine).observe(max(total_s, 0.0))
    except Exception:  # noqa: BLE001
        return


def is_native_repair_round(*, attempt: int, entry_req: object) -> bool:
    """CodeQa attempt>1 或定向修订视为 repair 轮次。"""
    return attempt > 1 or bool(entry_req)


def record_native_repair(engine: str, *, event: str, round: int) -> None:
    """event: attempted | codegen_ok | codegen_fail | qa_ok | qa_fail"""
    try:
        from app.core.metrics import NATIVE_ENGINE_REPAIR, NATIVE_ENGINE_REPAIR_ROUND

        NATIVE_ENGINE_REPAIR.labels(engine, event).inc()
        if event == "attempted":
            NATIVE_ENGINE_REPAIR_ROUND.labels(engine).observe(max(round, 1))
    except Exception:  # noqa: BLE001
        return
