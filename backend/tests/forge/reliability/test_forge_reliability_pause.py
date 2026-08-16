"""P0：pause_reason / recovery metadata（不改 RunStatus）。"""

from __future__ import annotations

import pytest
from app.enums import PauseReason, RunStatus
from app.forge.reliability.pause import (
    RecoveryInfo,
    apply_paused_metadata,
    build_pause_checkpoint,
    pause_reason_from_state,
)


def test_pause_reason_enum_values() -> None:
    assert PauseReason.WAITING_USER.value == "waiting_user"
    assert PauseReason.RECOVERABLE_ERROR.value == "recoverable_error"
    assert PauseReason.QUOTA_BLOCKED.value == "quota_blocked"
    assert PauseReason.MANUAL_HOLD.value == "manual_hold"


def test_build_pause_checkpoint_for_hitl() -> None:
    state = build_pause_checkpoint(
        phase="plan_confirm",
        pause_reason=PauseReason.WAITING_USER,
        design_doc={"title": "t"},
    )
    assert state["phase"] == "plan_confirm"
    assert state["pause_reason"] == "waiting_user"
    assert state["design_doc"]["title"] == "t"
    assert "recovery" not in state


def test_build_pause_checkpoint_for_recoverable() -> None:
    recovery = RecoveryInfo(
        node="code",
        error_code="provider_timeout",
        attempts=3,
        can_retry=True,
    )
    state = build_pause_checkpoint(
        phase="code",
        pause_reason=PauseReason.RECOVERABLE_ERROR,
        recovery=recovery,
    )
    assert state["pause_reason"] == "recoverable_error"
    assert state["recovery"] == {
        "node": "code",
        "error_code": "provider_timeout",
        "attempts": 3,
        "can_retry": True,
    }


def test_apply_paused_metadata_keeps_run_status_paused() -> None:
    class _Run:
        status = RunStatus.RUNNING.value

    run = _Run()
    apply_paused_metadata(run)  # type: ignore[arg-type]
    assert run.status == RunStatus.PAUSED.value


def test_pause_reason_from_state() -> None:
    assert pause_reason_from_state({"pause_reason": "waiting_user"}) == PauseReason.WAITING_USER
    assert pause_reason_from_state({}) is None
    with pytest.raises(ValueError):
        pause_reason_from_state({"pause_reason": "not_a_reason"})
