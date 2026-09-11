"""ask_user 工具协议（ADR-17）：解析 / 预算 / 相位与命令映射。"""

from __future__ import annotations

import json

from app.core.config import settings
from app.enums import RunCommandType
from app.forge.ask_user import (
    ASK_USER_CONTRACT,
    budget_remaining,
    budget_used,
    parse_ask_user,
    synthetic_answer,
)
from app.forge.commands import normalize_resume_command
from app.forge.hitl import allowed_commands_for, allowed_decisions_for, is_hitl_phase


def test_parse_valid_tool_call() -> None:
    out = parse_ask_user(
        json.dumps(
            {
                "tool": "ask_user",
                "reason": "题材决定玩法形态",
                "question": "想要单机闯关还是无尽生存？",
                "options": ["闯关", "生存"],
            }
        )
    )
    assert out is not None and out["options"] == ["闯关", "生存"]
    assert out["allow_free_text"] is True  # 默认允许


def test_parse_fenced_and_clamped() -> None:
    payload = json.dumps({"tool": "ask_user", "question": "Q?", "options": ["a", "b", "c", "d", "e", "f"]})
    fenced = f"```json\n{payload}\n```"
    out = parse_ask_user(fenced)
    assert out is not None and len(out["options"]) == 4  # 上限截断
    long = parse_ask_user(json.dumps({"tool": "ask_user", "question": "x" * 500}))
    assert long is None  # 问题超长 → 非法


def test_parse_rejects_non_tool_output() -> None:
    assert parse_ask_user("<!DOCTYPE html><html>") is None
    assert parse_ask_user(json.dumps({"format": "project"})) is None
    assert parse_ask_user(json.dumps({"tool": "other_tool", "question": "q"})) is None
    assert parse_ask_user("") is None


def test_budget_gate() -> None:
    assert budget_remaining({}) is True
    assert budget_used({"ask_user_count": 2}) == 2
    monkey = {"ask_user_count": settings.forge_ask_user_max_per_run}
    assert budget_remaining(monkey) is False
    assert "自行" in synthetic_answer()


def test_agent_question_phase_and_command_mapping() -> None:
    assert is_hitl_phase("agent_question")
    assert allowed_decisions_for("agent_question") == frozenset({"skip", "modify"})
    assert allowed_commands_for("agent_question") == (
        RunCommandType.REVISE_PLAN.value,
        RunCommandType.CANCEL_RUN.value,
    )
    # 回答与跳过都走 revise_plan；modify_text（feedback）承载回答
    for decision in ("modify", "skip"):
        normalized = normalize_resume_command(phase="agent_question", decision=decision)
        assert normalized.command_type is RunCommandType.REVISE_PLAN


def test_contract_mentions_memory_first() -> None:
    assert "MEMORY_DATA" in ASK_USER_CONTRACT  # 先查记忆再提问
    assert "禁止再问" in ASK_USER_CONTRACT
