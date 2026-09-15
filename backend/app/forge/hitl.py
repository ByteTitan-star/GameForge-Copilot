"""HITL phase vocabulary — single source of truth (ADR-10 / ADR-18)。

ADR-18 起固定确认门（plan_confirm / art_confirm）不再由图产生，仅保留一个
发布窗口供存量暂停中的 run resolve（LEGACY_PHASES），下个版本删除。
常驻相位：qa_failed / sandbox_failed（故障恢复暂停，非确认门）与
agent_question（模型经 ask_user 原生工具按需发起的提问暂停）。
"""

from __future__ import annotations

from app.enums import FailureClass, RunCommandType

HITL_PHASES = frozenset(
    {"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed", "agent_question"}
)

# 已取消的固定确认门（ADR-18）：仅可 resolve 存量暂停 run，图不再产生。
LEGACY_PHASES = frozenset({"plan_confirm", "art_confirm"})

# 常驻 HITL 相位：新流程唯一会产生暂停的相位集合。
ACTIVE_PHASES = HITL_PHASES - LEGACY_PHASES

_ALLOWED: dict[str, frozenset[str]] = {
    "plan_confirm": frozenset({"approve", "modify"}),
    "art_confirm": frozenset({"select_a", "select_b", "modify"}),
    "sandbox_failed": frozenset({"approve", "modify"}),
    "qa_failed": frozenset({"approve", "modify"}),
    # ADR-18：模型经 ask_user 工具主动提问；modify=回答（modify_text 承载），skip=让模型自行决策
    "agent_question": frozenset({"skip", "modify"}),
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
    "agent_question": (
        RunCommandType.ANSWER_QUESTION.value,
        RunCommandType.CANCEL_RUN.value,
    ),
}

_CROSS_STAGE_REPLAN_PHASES = frozenset({"qa_failed", "sandbox_failed"})


def is_hitl_phase(phase: str | None) -> bool:
    return phase in HITL_PHASES


def is_legacy_phase(phase: str | None) -> bool:
    """存量确认门相位：可 resolve，不再产生（ADR-18 过渡窗口）。"""
    return phase in LEGACY_PHASES


def allowed_decisions_for(phase: str) -> frozenset[str]:
    return _ALLOWED.get(phase, frozenset())


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
