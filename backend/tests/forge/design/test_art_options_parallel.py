"""并行美术方案：单方案解析与 A/B 聚合。"""

from __future__ import annotations

import pytest

from app.forge.art_direction import merge_parallel_art_options, parse_single_art_option


def test_parse_single_art_option_ok() -> None:
    raw = {
        "id": "A",
        "name": "纸面剪影",
        "summary": "用层叠剪影与纸质纹理表达跑酷节奏",
        "recommended": True,
    }
    out = parse_single_art_option(raw, expected_id="A")
    assert out["id"] == "A"
    assert out["recommended"] is True


def test_parse_single_rejects_wrong_id() -> None:
    with pytest.raises(ValueError, match="必须为 A"):
        parse_single_art_option(
            {"id": "B", "name": "x", "summary": "y" * 10, "recommended": False},
            expected_id="A",
        )


def test_merge_parallel_forces_exactly_one_recommended() -> None:
    a = {"id": "A", "name": "甲", "summary": "材料侧重叠纸与剪影", "recommended": True}
    b = {"id": "B", "name": "乙", "summary": "动效侧轨迹残影与节奏闪", "recommended": True}
    merged = merge_parallel_art_options(a, b)
    assert {o["id"] for o in merged["options"]} == {"A", "B"}
    assert sum(1 for o in merged["options"] if o["recommended"]) == 1
    assert merged["options"][0]["recommended"] is True  # A 优先


def test_merge_parallel_promotes_a_when_none_recommended() -> None:
    a = {"id": "A", "name": "甲", "summary": "材料侧重叠纸与剪影", "recommended": False}
    b = {"id": "B", "name": "乙", "summary": "动效侧轨迹残影与节奏闪", "recommended": False}
    merged = merge_parallel_art_options(a, b)
    assert merged["options"][0]["recommended"] is True
    assert merged["options"][1]["recommended"] is False
