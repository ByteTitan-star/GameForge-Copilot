"""HITL phase 词表 — 全仓库唯一真相源（ADR-10）。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
HITL = Human In The Loop：图跑到需要人确认 / 失败恢复时暂停，等人发命令再 resume。

本文件只回答三件事：
  1) 哪些 phase 算 HITL？（HITL_PHASES）
  2) 每个 phase 允许哪些「决策别名」？（approve / modify / select_a ...）
  3) 每个 phase 允许哪些正式 RunCommand？（APPROVE_PLAN / RETRY_INFRA ...）

禁止在 API / graph / games 各自维护一份影子集合 —— 改这里即可。

四个 HITL 阶段：
  plan_confirm   — 策划案出来，等人批准或修订
  art_confirm    — 美术方向选项出来，选 A/B 或修订
  sandbox_failed — 环境/基建失败，可重试 infra 或改实现
  qa_failed      — 试玩质量失败，可重试实现或回改策划

设计依据：docs/adr/ADR-10-checkpoint-hitl-idempotency.md
"""

from __future__ import annotations

from app.enums import FailureClass, RunCommandType

# 所有需要「等人」的 checkpoint.phase；resume 时也会识别这些
HITL_PHASES = frozenset({"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"})

# 前端/协议层用的短决策名 → 每个 phase 白名单
_ALLOWED: dict[str, frozenset[str]] = {
    "plan_confirm": frozenset({"approve", "modify"}),
    "art_confirm": frozenset({"select_a", "select_b", "modify"}),
    "sandbox_failed": frozenset({"approve", "modify"}),
    "qa_failed": frozenset({"approve", "modify"}),
}

# 正式命令枚举（写入 command 表 / API）；CANCEL 几乎总是可用
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

# 这些失败阶段允许「跨阶段回策划」—— 不是只在本阶段打转
_CROSS_STAGE_REPLAN_PHASES = frozenset({"qa_failed", "sandbox_failed", "art_confirm"})


def is_hitl_phase(phase: str | None) -> bool:
    """phase 是否属于 HITL 等待态。"""
    return phase in HITL_PHASES


def allowed_decisions_for(phase: str) -> frozenset[str]:
    """返回该 phase 允许的短决策名集合。"""
    return _ALLOWED[phase]


def allowed_commands_for(phase: str, failure_class: str | None = None) -> tuple[str, ...]:
    """返回该 phase 允许的正式命令列表。

    若 failure_class 属于「更该改策划」的类别（能力不匹配 / 验收不符 / 安全策略），
    会把 REVISE_PLAN 排到最前，作为建议首选。
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
    """是否允许从当前失败/确认阶段直接回改策划。"""
    return phase in _CROSS_STAGE_REPLAN_PHASES
