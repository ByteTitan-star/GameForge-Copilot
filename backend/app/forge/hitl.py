"""HITL phase vocabulary — single source of truth (ADR-10)."""

from __future__ import annotations

from app.enums import FailureClass, RunCommandType

HITL_PHASES = frozenset({"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"})

_ALLOWED: dict[str, frozenset[str]] = {
    "plan_confirm": frozenset({"approve", "modify"}),
    "art_confirm": frozenset({"select_a", "select_b", "modify"}),
    "sandbox_failed": frozenset({"approve", "modify"}),
    "qa_failed": frozenset({"approve", "modify"}),
}

_ALLOWED_COMMANDS: dict[str, tuple[str, ...]] = {
    "plan_confirm": (
        RunCommandType.APPROVE_PLAN.value,
        RunCommandType.REVISE_PLAN.value,
        RunCommandType.CANCEL_RUN.value,
    ),
    "art_confirm": (
        RunCommandType.SELECT_ART_A.value,
        RunCommandType.SELECT_ART_B.value,
        RunCommandType.REVISE_ART.value,
        RunCommandType.REVISE_PLAN.value,
        RunCommandType.CANCEL_RUN.value,
    ),
    "sandbox_failed": (
        RunCommandType.RETRY_INFRA.value,
        RunCommandType.RETRY_IMPLEMENTATION.value,
        RunCommandType.REVISE_PLAN.value,
        RunCommandType.CANCEL_RUN.value,
    ),
    "qa_failed": (
        RunCommandType.RETRY_IMPLEMENTATION.value,
        RunCommandType.REVISE_PLAN.value,
        RunCommandType.CANCEL_RUN.value,
    ),
}

_CROSS_STAGE_REPLAN_PHASES = frozenset({"qa_failed", "sandbox_failed", "art_confirm"})


def is_hitl_phase(phase: str | None) -> bool:
    return phase in HITL_PHASES


def allowed_decisions_for(phase: str) -> frozenset[str]:
    return _ALLOWED[phase]


def allowed_commands_for(phase: str, failure_class: str | None = None) -> tuple[str, ...]:
    base = list(_ALLOWED_COMMANDS.get(phase) or ())
    fc = (failure_class or "").strip().lower()
    preferred = RunCommandType.REVISE_PLAN.value
    if (
        fc
        in {
            FailureClass.CAPABILITY_MISMATCH.value,
            FailureClass.ACCEPTANCE_MISMATCH.value,
            FailureClass.POLICY_SECURITY.value,
        }
        and preferred in base
    ):
        return (preferred, *[cmd for cmd in base if cmd != preferred])
    return tuple(base)


def is_cross_stage_replan_phase(phase: str | None) -> bool:
    return phase in _CROSS_STAGE_REPLAN_PHASES
