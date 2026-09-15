"""ask_user 工具（ADR-18）：原生工具绑定，取代 ADR-17 的 inline JSON 文本协议。

设计要点：
- 工具 schema 以 OpenAI function 规范绑定给模型（provider 层双协议自动转换），
  "记忆优先"纪律写进 description：MEMORY_DATA（偏好）、设计稿、会话摘要能推导的禁止问；
- 平台侧执行 = 暂停为 agent_question 相位（复用 ADR-10 checkpoint/resume_grant 全套机制）；
- 预算 forge_ask_user_max_per_run 耗尽后**不再绑定工具**（模型物理上无法再问，
  取代旧版"注入合成回答重跑一次、再问即失败"）；
- 用户回答以 role:"tool" 消息回填（原生工具循环语义），并回流偏好抽取管道
  （回答是最强的 explicit 偏好信号——"有了偏好就不用再问"的闭环）；
- 参数校验失败按未调用处理（走产物解析路径，不 crash）。
"""

from __future__ import annotations

import json
from typing import Any

from app.core.config import settings

TOOL_NAME = "ask_user"

QUESTION_MAX = 200
REASON_MAX = 160
OPTION_MAX = 4
OPTION_LEN = 60

SYNTHETIC_ANSWER = (
    "（用户未作答：请依据已注入的偏好记忆、设计稿与会话信息自行做出最佳决策，"
    "不要再向用户提问，直接产出完整结果。）"
)

# 工具 schema：OpenAI function 规范（Anthropic 原生路径由 provider 层自动转换）。
ASK_USER_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": TOOL_NAME,
        "description": (
            "向用户提一个问题，澄清决策关键信息。仅当同时满足才可调用："
            "1) 缺失的信息会显著改变产物形态（题材方向、核心玩法取舍、内容分级等）；"
            "2) 无法从 MEMORY_DATA（用户偏好记忆）、既有设计稿或会话摘要推导。"
            "纪律：偏好（MEMORY_DATA）已覆盖的维度（风格/难度/语言/题材等）禁止再问；"
            "一次只问一个问题、最多 4 个选项；能自己合理决策的不要问；"
            "无需提问时正常输出产物，绝不调用本工具。"
        ),
        "parameters": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "为何必须问，一句话",
                    "maxLength": REASON_MAX,
                },
                "question": {
                    "type": "string",
                    "description": "问题，一句话",
                    "maxLength": QUESTION_MAX,
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string", "maxLength": OPTION_LEN},
                    "maxItems": OPTION_MAX,
                    "description": "候选选项（2-4 个）；允许自由回答时可留空",
                },
                "allow_free_text": {
                    "type": "boolean",
                    "description": "是否允许自由文本回答，默认 true",
                },
            },
            "required": ["reason", "question"],
        },
    },
}


def validate_ask_user_args(args: Any) -> dict[str, Any] | None:
    """校验工具参数（来源：模型 arguments JSON 已解析的 dict）。

    不合法返回 None：按未调用处理，调用方继续走产物解析路径（不 crash）。
    """
    if not isinstance(args, dict):
        return None
    question = str(args.get("question") or "").strip()
    if not question or len(question) > QUESTION_MAX:
        return None
    reason = str(args.get("reason") or "").strip()[:REASON_MAX]
    raw_options = args.get("options")
    raw_options = raw_options if isinstance(raw_options, list) else []
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
        "allow_free_text": args.get("allow_free_text") is not False,  # 默认允许
    }


def extract_ask_user_call(
    tool_calls: list[dict[str, Any]] | None,
) -> dict[str, Any] | None:
    """从模型返回的 tool_calls 中提取合法 ask_user 调用；无/不合法返回 None。"""
    if not tool_calls:
        return None
    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        func = call.get("function") or {}
        if str(func.get("name") or "") != TOOL_NAME:
            continue
        raw_args = func.get("arguments")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except (ValueError, TypeError):
            return None
        return validate_ask_user_args(args)
    return None


def budget_used(state: dict[str, Any]) -> int:
    return int(state.get("ask_user_count") or 0)


def budget_remaining(state: dict[str, Any]) -> bool:
    return budget_used(state) < max(0, int(settings.forge_ask_user_max_per_run))


def ask_messages(
    system: str,
    user_msg: str,
    *,
    question_payload: dict[str, Any],
    call_id: str,
    answer: str,
    tools: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """构造"带工具问答回填"的多轮消息（OpenAI 规范，provider 层按协议转换）。

    语义：模型此前通过 ask_user 发起提问（assistant tool_calls），用户已回答
    （role:"tool" 结果）。模型据此直接产出产物，无需重复上下文。
    """
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": TOOL_NAME,
                        "arguments": json.dumps(
                            question_payload, ensure_ascii=False
                        ),
                    },
                }
            ],
        },
        {"role": "tool", "tool_call_id": call_id, "content": answer or SYNTHETIC_ANSWER},
    ]


def synthetic_answer() -> str:
    return SYNTHETIC_ANSWER
