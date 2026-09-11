"""偏好目录（ADR-16 §3）：闭集槽位 = 偏好身份的唯一来源。

目录即 schema：槽位 id（如 visual.style）、类型（enum/bool）、枚举值、适用节点
（applies_to）。写路径第一步做别名归一 + 目录/类型校验，未命中者永不进入 active。
目录词表按需求证据加厚（note/归档行/eval 报告），不允许任何桶内开放 key。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# 适用节点：当前消费偏好的图节点（code/repair 默认不注入，不出现在 applies_to）
NODES = ("plan", "art")


@dataclass(frozen=True)
class Slot:
    key: str
    type: str  # enum | bool
    applies_to: tuple[str, ...]
    values: tuple[str, ...] = ()

    def validate_value(self, value: Any) -> str | None:
        """校验并规范化值；非法返回 None。"""
        text = str(value if value is not None else "").strip()
        if not text:
            return None
        if self.type == "bool":
            lowered = text.lower()
            if lowered in ("true", "1", "yes", "开", "是"):
                return "true"
            if lowered in ("false", "0", "no", "关", "否"):
                return "false"
            return None
        lowered = text.lower()
        return lowered if lowered in self.values else None


def _slot(key: str, values: tuple[str, ...], applies: tuple[str, ...], type_: str = "enum") -> Slot:
    return Slot(key=key, type=type_, applies_to=applies, values=values)


PREFERENCE_CATALOG: dict[str, Slot] = {
    s.key: s
    for s in (
        _slot(
            "visual.style",
            ("pixel", "pixel_retro_gb", "neon", "flat", "cartoon", "realistic", "minimalist"),
            ("art", "plan"),
        ),
        _slot(
            "visual.palette",
            ("dark", "light", "warm", "cool", "pastel", "high_contrast"),
            ("art",),
        ),
        _slot("visual.mood", ("cheerful", "calm", "epic", "eerie", "cute"), ("art", "plan")),
        _slot("ui.style", ("minimal", "hud_heavy", "retro"), ("art",)),
        _slot("ui.language", ("zh", "en"), ("art", "plan")),
        _slot(
            "gameplay.genre",
            (
                "platformer",
                "shooter",
                "puzzle",
                "racing",
                "roguelike",
                "tower_defense",
                "slice",
                "runner",
            ),
            ("plan",),
        ),
        _slot("gameplay.difficulty", ("easy", "normal", "hard", "hardcore"), ("plan",)),
        _slot("gameplay.pacing", ("relaxed", "standard", "intense"), ("plan",)),
        _slot("gameplay.session_length", ("short", "medium", "long"), ("plan",)),
        _slot("audio.muted", ("true", "false"), ("plan",), type_="bool"),
    )
}

CATALOG_VERSION = "2026-09-11.1"

# 别名归一（写路径第一步）：自由表述 → 目录槽位 key。
# 来源：ADR-15 记录的存量 key 分布 + 中文常见说法；小写子串匹配，命中即归一。
_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("visual_style", "visualstyle", "theme", "aesthetic", "look", "artistic_style"),
        "visual.style",
    ),
    (("palette", "color_scheme", "color", "配色"), "visual.palette"),
    (("mood", "atmosphere", "tone"), "visual.mood"),
    (("difficulty", "难度"), "gameplay.difficulty"),
    (("genre", "type", "题材", "类型"), "gameplay.genre"),
    (("pacing", "tempo", "节奏"), "gameplay.pacing"),
    (("session_length", "length", "时长"), "gameplay.session_length"),
    (("language", "lang", "语言"), "ui.language"),
    (("muted", "audio", "静音", "无声"), "audio.muted"),
)


def normalize_key(raw: str) -> str | None:
    """自由 key → 目录槽位 id；未命中返回 None（调用方必须拒绝进入 active）。"""
    text = (raw or "").strip().lower()
    if not text:
        return None
    if text in PREFERENCE_CATALOG:
        return text
    compact = re.sub(r"[\s_\-]+", "_", text)
    for needles, canonical in _ALIASES:
        for needle in needles:
            if needle in compact or needle in text:
                return canonical
    # 常见旧形态 'category.key' / 'category_key' 命中同名槽位尾段
    tail = compact.rsplit(".", 1)[-1].rsplit("_", 1)[-1]
    if tail in PREFERENCE_CATALOG:
        return tail
    return None


def slot_for(raw_key: str) -> Slot | None:
    return PREFERENCE_CATALOG.get(normalize_key(raw_key) or "")


def keys_for_node(node: str) -> tuple[str, ...]:
    """applies_to 含 node 的槽位 key（resolve_for 的目录侧输入）。"""
    normalized = (node or "").strip().lower().rstrip("*")  # 'plan*' → 'plan'
    return tuple(k for k, s in PREFERENCE_CATALOG.items() if normalized in s.applies_to)


def validate_candidate(raw_key: str, raw_value: Any) -> tuple[str, str] | None:
    """(归一 key, 规范值)；key 未知或值非法返回 None——写路径的唯一闸门。"""
    slot = slot_for(raw_key)
    if slot is None:
        return None
    value = slot.validate_value(raw_value)
    if value is None:
        return None
    return slot.key, value
