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
