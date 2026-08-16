"""可恢复暂停：status=paused + pause_reason/recovery（ADR-05）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.enums import PauseReason, RunStatus


class _StatusCarrier(Protocol):
    status: str


@dataclass(frozen=True, slots=True)
class RecoveryInfo:
    node: str
    error_code: str
    attempts: int
    can_retry: bool = True


def apply_paused_metadata(run: _StatusCarrier) -> None:
    """仅设置 status=paused，不引入新 RunStatus。"""
    run.status = RunStatus.PAUSED.value


def build_pause_checkpoint(
    *,
    phase: str,
    pause_reason: PauseReason,
    design_doc: dict[str, Any] | str | None = None,
    recovery: RecoveryInfo | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "phase": phase,
        "pause_reason": pause_reason.value,
    }
    if design_doc is not None:
        state["design_doc"] = design_doc
    if recovery is not None:
        state["recovery"] = asdict(recovery)
    if extra:
        state.update(extra)
    return state


def merge_pause_checkpoint(
    existing: dict[str, Any] | None,
    *,
    phase: str,
    pause_reason: PauseReason,
    design_doc: dict[str, Any] | str | None = None,
    recovery: RecoveryInfo | None = None,
    drop_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """以现有 checkpoint 为底覆盖暂停字段，避免丢掉 art/code 进度（ADR-10）。"""
    base = dict(existing or {})
    remove = drop_keys or frozenset({"pause_reason", "recovery"})
    for key in remove:
        base.pop(key, None)
    doc = design_doc if design_doc is not None else base.get("design_doc")
    return build_pause_checkpoint(
        phase=phase,
        pause_reason=pause_reason,
        design_doc=doc,
        recovery=recovery,
        extra={
            k: v
            for k, v in base.items()
            if k not in {"phase", "pause_reason", "recovery", "design_doc"}
        },
    )


def pause_reason_from_state(state: dict[str, Any] | None) -> PauseReason | None:
    if not state:
        return None
    raw = state.get("pause_reason")
    if raw is None:
        return None
    return PauseReason(str(raw))


def recovery_from_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    if not state:
        return None
    recovery = state.get("recovery")
    return dict(recovery) if isinstance(recovery, dict) else None
