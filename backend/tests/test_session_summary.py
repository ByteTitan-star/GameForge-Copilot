"""P1：Session Summary 触发与 schema。"""

from __future__ import annotations

from app.forge.memory.summary import (
    coerce_session_summary,
    empty_session_summary,
    should_refresh_summary,
)


def test_should_refresh_by_message_count() -> None:
    assert should_refresh_summary(message_count=21, historical_tokens=100) is True
    assert should_refresh_summary(message_count=20, historical_tokens=100) is False


def test_should_refresh_by_token_threshold() -> None:
    assert should_refresh_summary(message_count=5, historical_tokens=12_001) is True
    assert should_refresh_summary(message_count=5, historical_tokens=12_000) is False


def test_empty_summary_has_expected_keys() -> None:
    s = empty_session_summary()
    assert set(s) == {
        "current_goal",
        "confirmed_decisions",
        "rejected_options",
        "gameplay_constraints",
        "visual_constraints",
        "technical_constraints",
        "pending_requests",
    }


def test_coerce_session_summary_filters_unknown() -> None:
    raw = {
        "current_goal": "跑酷",
        "confirmed_decisions": ["一关"],
        "junk": 1,
        "pending_requests": "not-a-list",
    }
    out = coerce_session_summary(raw)
    assert out is not None
    assert out["current_goal"] == "跑酷"
    assert out["confirmed_decisions"] == ["一关"]
    assert out["pending_requests"] == []
