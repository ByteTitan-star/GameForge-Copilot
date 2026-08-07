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


def classify_entry_phase(requirement: str, *, has_prior_version: bool) -> EntryPhase:
    """规则路由：有历史版本且命中小改关键词 → code，否则 plan。"""
    if not has_prior_version:
        return EntryPhase.PLAN
    text = requirement.strip().lower()
    if any(h in requirement or h in text for h in _LARGE_CHANGE_HINTS):
        return EntryPhase.PLAN
    if any(h in requirement or h in text for h in _SMALL_CHANGE_HINTS):
        return EntryPhase.CODE
    return EntryPhase.PLAN
