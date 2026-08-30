"""智能迭代路由：根据 requirement 决定 entry_phase（Batch B · R5）。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
「第二次及以后改同一个游戏」时，不必每次都从策划重来。
本模块用关键词规则（无 LLM）把用户新需求分到：

  EntryPhase.PLAN  — 大改 / 无历史版本 / 默认：走完整策划
  EntryPhase.CODE  — 小改（颜色、数值、文案…）：可直接进 CodeQaLoop
  EntryPhase.CHAT  — 纯问答（怎么玩、解释…）：走 chat_reply，不生成

注意：策略表 policy.py 里有 "entry_router" 超时预算，
但当前主图并没有 add_node("entry_router")，而是用 graph.route_start
条件边 + 本函数的分类结果决定从哪进。读 graph._build_graph 时对照这里。
"""

from __future__ import annotations

from app.enums import EntryPhase

# 命中 → 视为大改，必须回策划
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

# 命中 → 视为小改，可跳过策划/美术直奔 code（仅当已有历史版本）
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

# 命中 → 问答，不触发生成管线
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
    """启发式：以 ?/？ 结尾，或包含问答关键词。"""
    text = req.strip()
    if not text:
        return False
    lower = text.lower()
    if text.endswith("?") or text.endswith("？"):
        return True
    return any(h in text or h in lower for h in _QUESTION_HINTS)


def classify_entry_phase(requirement: str | None, *, has_prior_version: bool) -> EntryPhase:
    """规则路由：有历史版本且命中小改关键词 → code；纯问答 → chat；否则 plan。

    无历史版本时一律 PLAN（第一次生成必须完整走策划）。
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
