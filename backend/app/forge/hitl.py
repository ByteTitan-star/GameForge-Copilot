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
    """判断 phase 是否为需人工介入的 HITL 阶段。

    场景：graph 中断判断、前端展示 HITL UI。
    参数：phase - 当前 checkpoint phase 字符串。
    返回：属于 plan_confirm/art_confirm/sandbox_failed/qa_failed 时为 True。
    """
    return phase in HITL_PHASES


def allowed_decisions_for(phase: str) -> frozenset[str]:
    """返回某 HITL phase 允许的 legacy decision 集合。

    场景：resolve_hitl API 校验用户决策合法性。
    参数：phase - HITL phase 名。
    返回：如 approve/modify/select_a 等的 frozenset。
    """
    return _ALLOWED[phase]


def allowed_commands_for(phase: str, failure_class: str | None = None) -> tuple[str, ...]:
    """返回某 HITL phase 允许的 RunCommandType 值列表。

    场景：前端渲染操作按钮；失败类为能力/验收/安全不匹配时优先展示改策划。
    参数：phase - HITL phase 名；failure_class - 可选失败分类。
    返回：RunCommandType.value 元组，按展示优先级排序。
    """
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
    """判断 phase 是否允许跨阶段改策划（受 replan_max_revisions 限制）。

    场景：``enqueue_resume`` 处理 REVISE_PLAN 时检查 replan 配额。
    参数：phase - 当前 checkpoint phase。
    返回：qa_failed/sandbox_failed/art_confirm 时为 True。
    """
    return phase in _CROSS_STAGE_REPLAN_PHASES
