"""ask_user 原生工具协议（ADR-18）：schema / 参数校验 / 提取 / 预算 / 相位与命令映射。"""

from __future__ import annotations

import json

from app.core.config import settings
from app.enums import RunCommandType
from app.forge.commands import normalize_resume_command
from app.forge.hitl import (
    ACTIVE_PHASES,
    LEGACY_PHASES,
    allowed_commands_for,
    allowed_decisions_for,
    is_hitl_phase,
)
from app.forge.tools import (
    ASK_USER_TOOL_SCHEMA,
    ask_messages,
    budget_remaining,
    budget_used,
    extract_ask_user_call,
    synthetic_answer,
    validate_ask_user_args,
)


def _tool_call(args: dict, name: str = "ask_user", call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
    }


def test_validate_valid_args() -> None:
    out = validate_ask_user_args(
        {
            "reason": "题材决定玩法形态",
            "question": "想要单机闯关还是无尽生存？",
            "options": ["闯关", "生存"],
        }
    )
    assert out is not None and out["options"] == ["闯关", "生存"]
    assert out["allow_free_text"] is True  # 默认允许


def test_validate_clamps_options_and_rejects_bad() -> None:
    out = validate_ask_user_args(
        {"question": "Q?", "options": ["a", "b", "c", "d", "e", "f"]}
    )
    assert out is not None and len(out["options"]) == 4  # 上限截断
    assert validate_ask_user_args({"question": "x" * 500}) is None  # 问题超长
    assert validate_ask_user_args({"reason": "no question"}) is None  # 缺问题
    assert validate_ask_user_args("not-a-dict") is None
    assert validate_ask_user_args(None) is None


def test_extract_ignores_other_tools_and_bad_args() -> None:
    assert extract_ask_user_call(None) is None
    assert extract_ask_user_call([]) is None
    # 非 ask_user 工具不拦截
    assert (
        extract_ask_user_call([_tool_call({"q": 1}, name="other_tool", call_id="c2")]) is None
    )
    # arguments 非法 JSON / 缺 question → 按未调用处理
    bad_json = {
        "id": "c3",
        "type": "function",
        "function": {"name": "ask_user", "arguments": "{not-json"},
    }
    assert extract_ask_user_call([bad_json]) is None
    assert extract_ask_user_call([_tool_call({"reason": "r"})]) is None


def test_extract_valid_tool_call() -> None:
    payload = extract_ask_user_call(
        [_tool_call({"question": "想要什么难度？", "options": ["简单", "困难"]}, call_id="c9")]
    )
    assert payload is not None
    assert payload["question"] == "想要什么难度？"
    assert payload["options"] == ["简单", "困难"]


def test_budget_gate() -> None:
    assert budget_remaining({}) is True
    assert budget_used({"ask_user_count": 2}) == 2
    monkey = {"ask_user_count": settings.forge_ask_user_max_per_run}
    assert budget_remaining(monkey) is False
    assert "自行" in synthetic_answer()


def test_agent_question_phase_and_command_mapping() -> None:
    assert is_hitl_phase("agent_question")
    assert "agent_question" in ACTIVE_PHASES
    assert allowed_decisions_for("agent_question") == frozenset({"skip", "modify"})
    assert allowed_commands_for("agent_question") == (
        RunCommandType.ANSWER_QUESTION.value,
        RunCommandType.CANCEL_RUN.value,
    )
    # 回答与跳过都是 answer_question；modify_text（feedback）承载回答
    for decision in ("modify", "skip"):
        normalized = normalize_resume_command(phase="agent_question", decision=decision)
        assert normalized.command_type is RunCommandType.ANSWER_QUESTION


def test_legacy_confirm_phases_resolvable_but_marked() -> None:
    """ADR-18 过渡窗口：固定确认门可 resolve（存量暂停 run）但标记 legacy。"""
    assert frozenset({"plan_confirm", "art_confirm"}) == LEGACY_PHASES
    assert is_hitl_phase("plan_confirm") and is_hitl_phase("art_confirm")
    assert "plan_confirm" not in ACTIVE_PHASES
    assert "art_confirm" not in ACTIVE_PHASES


def test_tool_schema_mentions_memory_first() -> None:
    desc = ASK_USER_TOOL_SCHEMA["function"]["description"]
    assert "MEMORY_DATA" in desc  # 先查记忆再提问
    assert "禁止再问" in desc
    assert ASK_USER_TOOL_SCHEMA["function"]["name"] == "ask_user"
    required = ASK_USER_TOOL_SCHEMA["function"]["parameters"]["required"]
    assert "question" in required and "reason" in required


def test_ask_messages_builds_tool_roundtrip() -> None:
    """问答回填消息：assistant(tool_calls) + role:tool（用户回答）。"""
    msgs = ask_messages(
        "SYS",
        "USER",
        question_payload={"tool": "ask_user", "question": "Q?", "options": []},
        call_id="ask_1",
        answer="像素风",
    )
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    assert msgs[2]["tool_calls"][0]["function"]["name"] == "ask_user"
    assert msgs[3]["tool_call_id"] == "ask_1"
    assert msgs[3]["content"] == "像素风"


def test_ask_messages_empty_answer_gets_synthetic() -> None:
    msgs = ask_messages(
        "SYS",
        "USER",
        question_payload={"tool": "ask_user", "question": "Q?"},
        call_id="ask_1",
        answer="",
    )
    assert msgs[3]["content"] == synthetic_answer()


def test_auto_select_art_picks_recommended() -> None:
    """ADR-18：无人值守自动选 recommended 项（解析层强制恰好一个）。"""
    from app.forge.graph import _auto_select_art

    opts_a_recommended = {
        "options": [
            {"id": "A", "name": "像素", "summary": "s", "recommended": True},
            {"id": "B", "name": "霓虹", "summary": "s", "recommended": False},
        ]
    }
    assert _auto_select_art(opts_a_recommended) == "select_a"
    opts_b_recommended = {
        "options": [
            {"id": "A", "name": "像素", "summary": "s", "recommended": False},
            {"id": "B", "name": "霓虹", "summary": "s", "recommended": True},
        ]
    }
    assert _auto_select_art(opts_b_recommended) == "select_b"
    # 防御性兜底：无 recommended 时默认 B（正常流程不会发生）
    assert _auto_select_art({"options": []}) == "select_b"
