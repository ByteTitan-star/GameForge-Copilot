"""Session Summary schema 与刷新触发（P1）。"""

from __future__ import annotations

from typing import Any, TypedDict


class SessionSummary(TypedDict, total=False):
    current_goal: str
    confirmed_decisions: list[str]
    rejected_options: list[str]
    gameplay_constraints: list[str]
    visual_constraints: list[str]
    technical_constraints: list[str]
    pending_requests: list[str]


def empty_session_summary() -> SessionSummary:
    return {
        "current_goal": "",
        "confirmed_decisions": [],
        "rejected_options": [],
        "gameplay_constraints": [],
        "visual_constraints": [],
        "technical_constraints": [],
        "pending_requests": [],
    }


def should_refresh_summary(
    *,
    message_count: int,
    historical_tokens: int,
    message_threshold: int = 20,
    token_threshold: int = 12_000,
) -> bool:
    """消息条数或历史 token 超阈则应刷新 summary。"""
    return message_count > message_threshold or historical_tokens > token_threshold


def coerce_session_summary(raw: Any) -> SessionSummary | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    base = empty_session_summary()
    for key in base:
        if key not in raw:
            continue
        val = raw[key]
        if key == "current_goal":
            base[key] = str(val or "")
        elif isinstance(val, list):
            base[key] = [str(x) for x in val]
    return base
