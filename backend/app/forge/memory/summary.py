"""Session Summary schema 与刷新触发（P1）。"""

from __future__ import annotations

from typing import Any, TypedDict

from app.forge.memory.context_builder import ContextTurn


class SessionSummary(TypedDict, total=False):
    """跨轮次会话摘要的结构化字段。

    持久化在 ``Game.session_summary_json``，由 ContextBuilder 以约 10% token 预算注入 prompt。
    """

    current_goal: str
    confirmed_decisions: list[str]
    rejected_options: list[str]
    gameplay_constraints: list[str]
    visual_constraints: list[str]
    technical_constraints: list[str]
    pending_requests: list[str]


def empty_session_summary() -> SessionSummary:
    """返回各字段为空列表/空串的默认 SessionSummary。

    场景：新建游戏、摘要解析失败回退、测试夹具初始化。
    返回：可安全写入 DB 的空摘要 dict。
    """
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
    """判断是否需要重新生成 Session Summary。

    场景：``refresh_session_summary_if_needed`` 在拼 prompt 前调用。
    参数：
        message_count - 该游戏累计 ForgeMessage 条数；
        historical_tokens - 最近对话 token 粗估；
        message_threshold - 消息条数阈值（默认 20）；
        token_threshold - 历史 token 阈值（默认 12000）。
    返回：True 表示应刷新摘要。
    """
    return message_count > message_threshold or historical_tokens > token_threshold


def coerce_session_summary(raw: Any) -> SessionSummary | None:
    """把 DB/JSON 中的原始值规范化为 SessionSummary。

    场景：从 ``game.session_summary_json`` 读取后、LLM 摘要 JSON 解析后。
    参数：raw - 任意 JSON 反序列化结果。
    返回：合法摘要 dict；无法识别时返回 None。
    """
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

    场景：默认摘要路径；LLM 摘要失败时的回退；未配置 ``memory_session_summary_llm`` 时。
    参数：
        turns - 按时间正序的对话轮次；
        previous - 上一轮已持久化的摘要（用于增量合并）。
    返回：新的 SessionSummary（会截断单条文本长度以防膨胀）。

    P1 默认路径；昂贵的 LLM 摘要可后置为可选增强，不得阻塞 Memory MVP。
    """
    out = empty_session_summary()
    if previous:
        for key, val in previous.items():
            if key == "current_goal" and isinstance(val, str):
                out["current_goal"] = val
            elif isinstance(val, list):
                out[key] = list(val)  # type: ignore[literal-required]

    user_texts = [t.content.strip() for t in turns if t.role == "user" and t.content.strip()]
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
    """向摘要列表追加非空且未出现过的字符串。

    场景：``synthesize_summary_from_turns`` 归类约束时去重。
    参数：items - 目标列表（原地修改）；value - 待追加文本。
    返回：无。
    """
    if value and value not in items:
        items.append(value)


def _clip(text: str, n: int) -> str:
    """按字符数截断文本，超出时加省略号。

    场景：摘要各字段长度上限控制。
    参数：text - 原文；n - 最大字符数（含省略号占位）。
    返回：截断后的字符串。
    """
    text = text.strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rstrip() + "…"
