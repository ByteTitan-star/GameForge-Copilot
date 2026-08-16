"""可选 LLM Session Summary（P1 尾巴；默认关，失败回落确定性 synthesizer）。"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.forge.memory.context_builder import ContextTurn
from app.forge.memory.summary import (
    SessionSummary,
    coerce_session_summary,
    empty_session_summary,
    synthesize_summary_from_turns,
)

LlmComplete = Callable[[str, str], Awaitable[str]]

_SUMMARY_SYSTEM = """
你是游戏创作会话摘要器。根据对话轮次输出一个合法 JSON 对象（不要 Markdown），字段仅限：
current_goal(string), confirmed_decisions(list[string]), rejected_options(list[string]),
gameplay_constraints(list[string]), visual_constraints(list[string]),
technical_constraints(list[string]), pending_requests(list[string])。
只保留对后续生成有用的稳定约定；不要发明未出现的事实。
""".strip()


async def synthesize_summary_via_llm(
    turns: list[ContextTurn],
    previous: SessionSummary | None,
    *,
    complete: LlmComplete,
) -> SessionSummary:
    """调用 LLM 生成 SessionSummary；解析失败则回落确定性 synthesizer。"""
    user_msg = _build_user_message(turns, previous)
    try:
        raw = await complete(_SUMMARY_SYSTEM, user_msg)
        parsed = _parse_summary_json(raw)
        coerced = coerce_session_summary(parsed)
        if coerced is not None:
            return coerced
    except Exception:  # noqa: BLE001 摘要增强失败不得阻断 Memory
        pass
    return synthesize_summary_from_turns(turns, previous=previous)


def _build_user_message(
    turns: list[ContextTurn], previous: SessionSummary | None
) -> str:
    lines = ["【Recent Turns】"]
    for t in turns[-30:]:
        lines.append(f"{t.role}: {t.content.strip()[:400]}")
    if previous:
        lines.append("【Previous Summary】")
        lines.append(json.dumps(previous, ensure_ascii=False))
    lines.append("请输出更新后的 Session Summary JSON。")
    return "\n".join(lines)


def _parse_summary_json(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        return dict(empty_session_summary())
    return data
