"""P1：Session Summary 合成与刷新。"""

from __future__ import annotations

from app.forge.memory.context_builder import ContextTurn, estimate_tokens
from app.forge.memory.summary import (
    coerce_session_summary,
    empty_session_summary,
    should_refresh_summary,
    synthesize_summary_from_turns,
)


def test_synthesize_sets_goal_from_latest_user_turn() -> None:
    turns = [
        ContextTurn(role="user", content="做一个跑酷"),
        ContextTurn(role="assistant", content="设计方案已生成"),
        ContextTurn(role="user", content="改成双人合作"),
    ]
    summary = synthesize_summary_from_turns(turns, previous=None)
    assert summary["current_goal"] == "改成双人合作"
    assert "做一个跑酷" in summary["confirmed_decisions"] or summary["pending_requests"]


def test_synthesize_merges_previous_constraints() -> None:
    prev = empty_session_summary()
    prev["visual_constraints"] = ["像素风"]
    prev["confirmed_decisions"] = ["一关"]
    turns = [ContextTurn(role="user", content="以后都用像素风，再加一关")]
    summary = synthesize_summary_from_turns(turns, previous=prev)
    assert "像素风" in summary["visual_constraints"]
    assert summary["current_goal"]


def test_coerce_roundtrip_after_synthesize() -> None:
    turns = [ContextTurn(role="user", content="平台跳跃")]
    raw = synthesize_summary_from_turns(turns, previous=None)
    coerced = coerce_session_summary(raw)
    assert coerced is not None
    assert coerced["current_goal"] == "平台跳跃"


def test_should_refresh_still_holds() -> None:
    assert should_refresh_summary(message_count=21, historical_tokens=10) is True
    tokens = estimate_tokens("x" * 50_000)
    assert should_refresh_summary(message_count=1, historical_tokens=tokens) is True
