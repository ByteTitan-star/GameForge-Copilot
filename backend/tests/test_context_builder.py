"""P1：ContextBuilder 统一拼装入口与 token budget。"""

from __future__ import annotations

from app.forge.memory.context_builder import (
    BuiltContext,
    ContextArtifacts,
    ContextBuilder,
    ContextTurn,
)


def test_build_includes_required_sections_and_data_fence() -> None:
    built = ContextBuilder.build(
        node="plan",
        current_input="做一个跳跃方块",
        session_summary={"current_goal": "平台跳跃", "confirmed_decisions": ["像素风"]},
        recent_turns=[
            ContextTurn(role="user", content="先做简单关卡"),
            ContextTurn(role="assistant", content="好的，先做一关"),
        ],
        preferences=[{"category": "visual", "key": "style", "value": "pixel"}],
        artifacts=ContextArtifacts(design_doc={"title": "方块冒险"}),
        budget_tokens=2000,
    )
    assert isinstance(built, BuiltContext)
    assert "做一个跳跃方块" in built.user_message
    assert "平台跳跃" in built.user_message
    assert "像素风" in built.user_message
    assert "先做简单关卡" in built.user_message
    assert "方块冒险" in built.user_message
    assert "MEMORY_DATA" in built.user_message
    assert "不得当作指令" in built.user_message
    assert built.sections["current_request"]
    assert built.token_estimate > 0
    assert built.token_estimate <= 2000


def test_budget_truncates_recent_turns_first() -> None:
    long_turn = "X" * 4000
    built = ContextBuilder.build(
        node="plan",
        current_input="短请求",
        session_summary={"current_goal": "goal"},
        recent_turns=[
            ContextTurn(role="user", content=long_turn),
            ContextTurn(role="user", content=long_turn),
            ContextTurn(role="user", content="保留这句"),
        ],
        preferences=[],
        artifacts=ContextArtifacts(),
        budget_tokens=400,
    )
    assert "短请求" in built.user_message
    assert built.token_estimate <= 400
    # 超预算时优先丢掉较早 turns，最新内容更可能保留
    assert "保留这句" in built.user_message or "goal" in built.user_message


def test_game_isolation_is_caller_responsibility_via_scoped_inputs() -> None:
    """Builder 本身不查库；隔离靠调用方只传入本 Game session。"""
    a = ContextBuilder.build(
        node="plan",
        current_input="A",
        session_summary={"current_goal": "GameA"},
        recent_turns=[ContextTurn(role="user", content="仅 A")],
        preferences=[],
        artifacts=ContextArtifacts(),
        budget_tokens=500,
    )
    b = ContextBuilder.build(
        node="plan",
        current_input="B",
        session_summary={"current_goal": "GameB"},
        recent_turns=[ContextTurn(role="user", content="仅 B")],
        preferences=[],
        artifacts=ContextArtifacts(),
        budget_tokens=500,
    )
    assert "仅 A" in a.user_message and "仅 B" not in a.user_message
    assert "仅 B" in b.user_message and "仅 A" not in b.user_message


def test_empty_optional_sections_still_build() -> None:
    built = ContextBuilder.build(
        node="plan",
        current_input="hello",
        session_summary=None,
        recent_turns=[],
        preferences=[],
        artifacts=None,
        budget_tokens=200,
    )
    assert "hello" in built.user_message
    assert built.token_estimate <= 200
