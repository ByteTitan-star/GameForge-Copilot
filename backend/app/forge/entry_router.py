"""智能迭代路由：根据 requirement 决定 entry_phase（Batch B · R5）。"""

from __future__ import annotations

from app.enums import EntryPhase

_LARGE_CHANGE_HINTS = (
    "新关卡",
    "新玩法",
    "重写",
    "换核心",
    "boss",
    "机制",
    "关卡结构",
    "redesign",
    "rewrite",
    "new level",
    "new mechanic",
)

_SMALL_CHANGE_HINTS = (
    "颜色",
    "背景",
    "改",
    "调",
    "数值",
    "分数",
    "文案",
    "文字",
    "按钮",
    "purple",
    "color",
    "background",
    "score",
    "text",
    "fix",
    "bug",
    "微调",
)

_QUESTION_HINTS = (
    "什么意思",
    "是什么",
    "解释",
    "怎么玩",
    "如何玩",
    "玩法是什么",
    "看不懂",
    "不明白",
    "告诉我",
    "explain",
    "what is",
    "how to play",
    "how do i play",
    "tell me about",
)


def _looks_like_question(req: str) -> bool:
    """判断用户 requirement 是否更像问答而非修改指令。

    作用：检测问号结尾或常见疑问关键词。
    场景：classify_entry_phase 在已有版本时区分 chat 与 code/plan。
    参数：req - 用户 requirement 原文。
    返回：True 表示应走 EntryPhase.CHAT。
    """
    text = req.strip()
    if not text:
        return False
    lower = text.lower()
    if text.endswith("?") or text.endswith("？"):
        return True
    return any(h in text or h in lower for h in _QUESTION_HINTS)


def classify_entry_phase(requirement: str | None, *, has_prior_version: bool) -> EntryPhase:
    """根据 requirement 与是否有历史版本决定入口阶段。

    作用：规则路由：大改→plan、小改→code、纯问答→chat。
    场景：games/services.create_run 写入 GenerationRun.entry_phase。
    参数：requirement - 本轮用户输入；has_prior_version - 是否已有 current_version。
    返回：EntryPhase（PLAN / CODE / CHAT）。
    """
    if not has_prior_version:
        return EntryPhase.PLAN
    req = (requirement or "").strip()
    if _looks_like_question(req):
        return EntryPhase.CHAT
    text = req.lower()
    if any(h in req or h in text for h in _LARGE_CHANGE_HINTS):
        return EntryPhase.PLAN
    if any(h in req or h in text for h in _SMALL_CHANGE_HINTS):
        return EntryPhase.CODE
    return EntryPhase.PLAN
