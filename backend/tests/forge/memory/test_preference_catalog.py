"""偏好目录（ADR-16）：闭集槽位、别名归一、类型校验、按节点 key 集。"""

from __future__ import annotations

from app.forge.memory.catalog import (
    keys_for_node,
    normalize_key,
    slot_for,
    validate_candidate,
)


def test_normalize_key_direct_and_alias() -> None:
    assert normalize_key("visual.style") == "visual.style"
    assert normalize_key("Theme") == "visual.style"  # 别名
    assert normalize_key("artistic_style.visual_expressiveness") == "visual.style"  # 旧叙事形态
    assert normalize_key("难度") == "gameplay.difficulty"
    assert normalize_key(" Visual Style ") == "visual.style"  # 大小写/空白
    assert normalize_key("totally_unknown") is None


def test_validate_candidate_rejects_unknown_and_bad_value() -> None:
    assert validate_candidate("visual.style", "Pixel") == ("visual.style", "pixel")
    assert validate_candidate("theme", "neon") == ("visual.style", "neon")  # 别名归一后校验
    assert validate_candidate("visual.style", "watercolor") is None  # 枚举外
    assert validate_candidate("no_such_key", "x") is None  # 目录外
    assert validate_candidate("audio.muted", True) == ("audio.muted", "true")  # 布尔规范化
    assert validate_candidate("audio.muted", "sure") is None


def test_keys_for_node_scopes_injection() -> None:
    plan_keys = keys_for_node("plan")
    art_keys = keys_for_node("art")
    assert "gameplay.difficulty" in plan_keys and "gameplay.difficulty" not in art_keys
    assert "visual.palette" in art_keys and "visual.palette" not in plan_keys
    assert "visual.style" in plan_keys and "visual.style" in art_keys  # 跨切槽位
    assert keys_for_node("plan*") == plan_keys  # 图节点名带通配后缀
    assert keys_for_node("code") == ()  # code/repair 默认无注入


def test_slot_metadata() -> None:
    slot = slot_for("gameplay.difficulty")
    assert slot is not None and slot.type == "enum"
    assert set(slot.applies_to) == {"plan"}
