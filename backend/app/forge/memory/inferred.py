"""P1 尾巴：Inferred 偏好抽取（弱信号；不得覆盖 Explicit）。"""

from __future__ import annotations

import re
from typing import Any

from app.forge.memory.explicit import looks_like_explicit_preference

# 无「以后/默认」等显式标记时，仍可从重复风格/难度措辞推断弱偏好
_INFERRED_HINTS: list[tuple[re.Pattern[str], str, str, dict[str, Any]]] = [
    (re.compile(r"像素|pixel", re.I), "visual", "style", {"style": "pixel"}),
    (re.compile(r"卡通", re.I), "visual", "style", {"style": "cartoon"}),
    (re.compile(r"手绘", re.I), "visual", "style", {"style": "hand_drawn"}),
    (re.compile(r"简单|休闲|难度低", re.I), "gameplay", "difficulty", {"difficulty": "easy"}),
    (re.compile(r"硬核|很难|高难度", re.I), "gameplay", "difficulty", {"difficulty": "hard"}),
    (re.compile(r"静音|不要.*音效|无声", re.I), "audio", "muted", {"muted": True}),
]


def extract_inferred_preferences(text: str) -> list[dict[str, Any]]:
    """从单次需求推断弱偏好（不得覆盖 Explicit）。

    场景：规则引擎遗留路径；已含 Explicit 触发词则返回空交给 explicit 路径。
    参数：text - 用户消息文本。
    返回：含 source=inferred、confidence=0.4 的偏好 dict 列表。
    """
    raw = (text or "").strip()
    if not raw or looks_like_explicit_preference(raw):
        return []
    found: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for pattern, category, key, value in _INFERRED_HINTS:
        if not pattern.search(raw):
            continue
        pair = (category, key)
        if pair in seen:
            continue
        seen.add(pair)
        found.append(
            {
                "category": category,
                "key": key,
                "value_json": {**value, "evidence": {"kind": "utterance"}},
                "source": "inferred",
                "confidence": 0.4,
                "status": "active",
            }
        )
    return found
