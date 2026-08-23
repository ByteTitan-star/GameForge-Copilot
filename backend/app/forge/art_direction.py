"""美术 Agent 的结构化输出解析与校验。"""

from __future__ import annotations

import json
from typing import Any


def _decode_object(raw: Any) -> dict[str, Any]:
    """将 LLM 美术输出解析为 dict；支持 Markdown 围栏与首尾杂质剥离。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        raise ValueError("美术输出必须是 JSON 对象")
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline >= 0 else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("美术输出不是合法 JSON") from None
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("美术输出不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("美术输出必须是 JSON 对象")
    return value


def parse_art_options(raw: Any) -> dict[str, list[dict[str, Any]]]:
    """解析两个简短方向，严格保证 A/B 与唯一推荐项。"""
    value = _decode_object(raw)
    options = value.get("options")
    if not isinstance(options, list) or len(options) != 2:
        raise ValueError("art options 必须恰好包含两个方案")

    parsed: list[dict[str, Any]] = []
    for item in options:
        if not isinstance(item, dict):
            raise ValueError("每个美术方案必须是对象")
        option_id = str(item.get("id") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        summary = str(item.get("summary") or "").strip()
        recommended = item.get("recommended")
        if option_id not in {"A", "B"}:
            raise ValueError("美术方案 id 必须为 A 或 B")
        if not name or not summary:
            raise ValueError(f"美术方案 {option_id} 缺少 name 或 summary")
        if not isinstance(recommended, bool):
            raise ValueError(f"美术方案 {option_id}.recommended 必须是布尔值")
        parsed.append(
            {
                "id": option_id,
                "name": name[:40],
                "summary": summary[:500],
                "recommended": recommended,
            }
        )

    if {item["id"] for item in parsed} != {"A", "B"}:
        raise ValueError("美术方案必须分别为 A 和 B")
    if sum(bool(item["recommended"]) for item in parsed) != 1:
        raise ValueError("两个美术方案中必须恰好有一个推荐项")
    parsed.sort(key=lambda item: item["id"])
    return {"options": parsed}


def parse_art_detail(raw: Any, selected_option: str) -> dict[str, Any]:
    """解析用户选定方向的实现级设计稿。"""
    value = _decode_object(raw)
    value["selected_option"] = selected_option.upper()
    required_text = ("name", "visual_concept")
    required_lists = (
        "implementation_principles",
        "screens",
        "hud",
        "entities",
        "effects",
        "responsive",
        "accessibility",
        "performance",
        "acceptance_criteria",
    )
    missing = [key for key in required_text if not str(value.get(key) or "").strip()]
    missing += [
        key for key in required_lists if not isinstance(value.get(key), list) or not value[key]
    ]
    if not isinstance(value.get("palette"), dict) or not value["palette"]:
        missing.append("palette")
    if not isinstance(value.get("typography"), dict) or not value["typography"]:
        missing.append("typography")
    if missing:
        raise ValueError("详细美术设计稿缺少有效字段：" + ", ".join(missing))
    return value


__all__ = ["parse_art_detail", "parse_art_options"]
