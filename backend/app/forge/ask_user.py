"""ask_user 内联工具协议（ADR-17 / issue #169）：模型按需向用户提问。

协议：节点本轮的**完整输出**是单个 JSON 对象
  {"tool":"ask_user","reason":str,"question":str,"options":[str,...],"allow_free_text":bool}
平台解析后暂停为 agent_question 相位；用户回答经既有 revise 通道回流。
护栏：shape 不符视为普通产物输出（走既有解析路径，不 crash）；
每 run 预算 forge_ask_user_max_per_run，耗尽后注入合成回答自动继续。
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings

TOOL_NAME = "ask_user"

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")

QUESTION_MAX = 200
REASON_MAX = 160
OPTION_MAX = 4
OPTION_LEN = 60

SYNTHETIC_ANSWER = (
    "（用户未作答：请依据已注入的偏好记忆、设计稿与会话信息自行做出最佳决策，"
    "不要再向用户提问，直接产出完整结果。）"
)

# 工具契约（拼进 plan 提示；先查记忆再考虑提问）
ASK_USER_CONTRACT = (
    "【ask_user 工具（可选）】\n"
    "如果在动手前发现某项**决策关键**信息缺失，且无法从 MEMORY_DATA（用户偏好）、"
    "既有设计稿或会话摘要中推导，你可以且仅可以输出下面这一种 JSON 来向用户提问：\n"
    '{"tool":"ask_user","reason":"<为何必须问，一句话>","question":"<问题，一句话>",'
    '"options":["选项A","选项B"],"allow_free_text":true}\n'
    "纪律：\n"
    "1. 偏好（MEMORY_DATA）已覆盖的维度（风格/难度/语言/题材等）禁止再问。\n"
    "2. 一次最多问一个问题、最多 4 个选项；能自己合理决策的不要问。\n"
    "3. 若无需提问，正常输出设计稿 JSON——绝不要输出 ask_user 之外的任何工具。\n"
)


class AskUserRequested(Exception):
    """节点输出了合法 ask_user 工具调用（payload 为解析结果）。"""

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__(payload.get("question") or "ask_user")
        self.payload = payload


def parse_ask_user(raw: str) -> dict[str, Any] | None:
    """严格解析；不合法返回 None（调用方按普通产物处理）。"""
    text = (raw or "").strip()
    stripped = _FENCE_RE.sub("", text).strip()
    if stripped.startswith("json"):
        stripped = stripped[4:].strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("tool") != TOOL_NAME:
        return None
    question = str(data.get("question") or "").strip()
    if not question or len(question) > QUESTION_MAX:
        return None
    reason = str(data.get("reason") or "").strip()[:REASON_MAX]
    raw_opt = data.get("options")
    raw_options = raw_opt if isinstance(raw_opt, list) else []
    options: list[str] = []
    for opt in raw_options:
        text_opt = str(opt or "").strip()[:OPTION_LEN]
        if text_opt and text_opt not in options:
            options.append(text_opt)
        if len(options) >= OPTION_MAX:
            break
    return {
        "tool": TOOL_NAME,
        "reason": reason,
        "question": question,
        "options": options,
        "allow_free_text": data.get("allow_free_text") is not False,  # 默认允许
    }


def budget_used(state: dict[str, Any]) -> int:
    return int(state.get("ask_user_count") or 0)


def budget_remaining(state: dict[str, Any]) -> bool:
    return budget_used(state) < max(0, int(settings.forge_ask_user_max_per_run))


def synthetic_answer() -> str:
    return SYNTHETIC_ANSWER
