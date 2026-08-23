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
    """调用 LLM 生成 Session Summary，失败则回落确定性 synthesizer。

    场景：配置 ``memory_session_summary_llm`` 时的增强摘要路径。
    参数：
        turns - 近期对话轮次；
        previous - 上一轮已持久化的摘要；
        complete - 异步 LLM 补全函数 (system, user) -> str。
    返回：LLM 解析成功则返回 coerced 摘要，否则回落 synthesize_summary_from_turns。
    """
    user_msg = _build_user_message(turns, previous)
    try:
        raw = await complete(_SUMMARY_SYSTEM, user_msg)
        parsed = _parse_summary_json(raw)
        coerced = coerce_session_summary(parsed)
        if coerced is not None:
            return coerced
    except Exception:  # noqa: BLE001 摘要增强失败不得阻断 Memory  # nosec B110
        pass
    return synthesize_summary_from_turns(turns, previous=previous)


def _build_user_message(turns: list[ContextTurn], previous: SessionSummary | None) -> str:
    """拼装 LLM 摘要请求的用户消息。

    场景：``synthesize_summary_via_llm`` 调用 LLM 前构造 prompt。
    参数：turns - 对话轮次；previous - 上一轮摘要或 None。
    返回：含 Recent Turns、Previous Summary 与指令的多行文本。
    """
    lines = ["【Recent Turns】"]
    for t in turns[-30:]:
        lines.append(f"{t.role}: {t.content.strip()[:400]}")
    if previous:
        lines.append("【Previous Summary】")
        lines.append(json.dumps(previous, ensure_ascii=False))
    lines.append("请输出更新后的 Session Summary JSON。")
    return "\n".join(lines)


def _parse_summary_json(raw: str) -> dict[str, Any]:
    """解析 LLM 返回的 Session Summary JSON（支持 Markdown 代码块包裹）。

    场景：``synthesize_summary_via_llm`` 解析 LLM 输出。
    参数：raw - LLM 原始响应文本。
    返回：解析后的 dict；非 dict 时返回空摘要结构。
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if not isinstance(data, dict):
        return dict(empty_session_summary())
    return data
