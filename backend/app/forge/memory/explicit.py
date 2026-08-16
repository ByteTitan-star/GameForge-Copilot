"""P1：Explicit 偏好抽取（关键词命中 + schema）。"""

from __future__ import annotations

import re
from typing import Any

# 显式偏好触发词（中文）；命中后才尝试抽取，避免把单次需求当长期偏好
_EXPLICIT_MARKERS = re.compile(
    r"(以后|我喜欢|默认|每次都|不要再|总是|一律|固定)",
)

# 粗粒度类别推断
_CATEGORY_HINTS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"像素|pixel", re.I), "visual", "style"),
    (re.compile(r"卡通|手绘", re.I), "visual", "style"),
    (re.compile(r"不要再.*音|静音|无声", re.I), "audio", "muted"),
    (re.compile(r"简单|难度低|休闲", re.I), "gameplay", "difficulty"),
    (re.compile(r"难|硬核", re.I), "gameplay", "difficulty"),
]


def looks_like_explicit_preference(text: str) -> bool:
    return bool(_EXPLICIT_MARKERS.search(text or ""))


def extract_explicit_preferences(text: str) -> list[dict[str, Any]]:
    """从用户文本抽取 Explicit 偏好；无触发词则返回空。

    返回结构对齐 user_preferences 写入字段（category/key/value_json）。
    """
    raw = (text or "").strip()
    if not raw or not looks_like_explicit_preference(raw):
        return []
    found: list[dict[str, Any]] = []
    for pattern, category, key in _CATEGORY_HINTS:
        if pattern.search(raw):
            value = _value_for(category, key, raw)
            found.append(
                {
                    "category": category,
                    "key": key,
                    "value_json": value,
                    "source": "explicit",
                    "confidence": 0.8,
                    "status": "active",
                }
            )
    if found:
        return found
    # 命中触发词但未匹配类别：落入 generic note，供用户后续编辑
    return [
        {
            "category": "general",
            "key": "note",
            "value_json": {"text": raw[:500]},
            "source": "explicit",
            "confidence": 0.5,
            "status": "active",
        }
    ]


def _value_for(category: str, key: str, text: str) -> dict[str, Any]:
    if category == "visual" and key == "style":
        if re.search(r"像素|pixel", text, re.I):
            return {"style": "pixel"}
        if re.search(r"卡通", text):
            return {"style": "cartoon"}
        if re.search(r"手绘", text):
            return {"style": "hand_drawn"}
        return {"style": "custom", "raw": text[:200]}
    if category == "audio" and key == "muted":
        return {"muted": True}
    if category == "gameplay" and key == "difficulty":
        if re.search(r"难|硬核", text):
            return {"difficulty": "hard"}
        return {"difficulty": "easy"}
    return {"text": text[:200]}
