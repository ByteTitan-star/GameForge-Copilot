"""Session Summary schema 与刷新触发（P1）。"""

from __future__ import annotations

from typing import Any, TypedDict

from app.forge.memory.context_builder import ContextTurn


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


def synthesize_summary_from_turns(
    turns: list[ContextTurn],
    *,
    previous: SessionSummary | None,
) -> SessionSummary:
    """无 LLM 的确定性摘要：从对话轮次提炼结构化 Session Summary。

    P1 默认路径；昂贵的 LLM 摘要可后置为可选增强，不得阻塞 Memory MVP。
    """
    out = empty_session_summary()
    if previous:
        for key, val in previous.items():
            if key == "current_goal" and isinstance(val, str):
                out["current_goal"] = val
            elif isinstance(val, list):
                out[key] = list(val)  # type: ignore[literal-required]

    user_texts = [
        t.content.strip() for t in turns if t.role == "user" and t.content.strip()
    ]
    if user_texts:
        out["current_goal"] = _clip(user_texts[-1], 200)
        earlier = user_texts[:-1][-5:]
        for text in earlier:
            _append_unique(out["confirmed_decisions"], _clip(text, 120))

    for text in user_texts[-8:]:
        low = text.lower()
        if any(k in text for k in ("像素", "卡通", "手绘")) or "pixel" in low:
            _append_unique(out["visual_constraints"], _clip(text, 80))
        if any(k in text for k in ("难度", "简单", "硬核", "关卡")):
            _append_unique(out["gameplay_constraints"], _clip(text, 80))
        if any(k in text for k in ("引擎", "phaser", "pixi", "canvas", "vite")):
            _append_unique(out["technical_constraints"], _clip(text, 80))
        if any(k in text for k in ("不要", "别再", "取消")):
            _append_unique(out["rejected_options"], _clip(text, 80))
        if any(k in text for k in ("还要", "另外", "待会", "之后再")):
            _append_unique(out["pending_requests"], _clip(text, 80))

    return out


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _clip(text: str, n: int) -> str:
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"
