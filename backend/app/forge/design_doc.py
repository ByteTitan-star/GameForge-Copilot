"""策划稿结构化解析（Batch A · B-A4）。"""

from __future__ import annotations

import json
from typing import Any


def normalize_design_doc(obj: dict[str, Any], fallback_title: str) -> dict[str, Any]:
    levels = obj.get("levels") or []
    if not isinstance(levels, list):
        levels = [str(levels)]
    return {
        "title": str(obj.get("title") or fallback_title),
        "gameplay": str(obj.get("gameplay") or ""),
        "controls": str(obj.get("controls") or "见设计稿"),
        "levels": [str(x) for x in levels],
    }


def parse_design_doc(raw: str, fallback_title: str) -> dict[str, Any]:
    """LLM 输出 → 结构化 design_doc；失败时整段文本 fallback 到 gameplay。"""
    text = raw.strip()
    if not text:
        return normalize_design_doc({}, fallback_title)

    candidates: list[str] = [text]
    if "```" in text:
        for block in text.split("```"):
            chunk = block.strip()
            if chunk.startswith("json"):
                chunk = chunk[4:].strip()
            if chunk.startswith("{"):
                candidates.append(chunk)

    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return normalize_design_doc(obj, fallback_title)

    return normalize_design_doc({"gameplay": text}, fallback_title)


def design_doc_to_text(doc: dict[str, Any] | str) -> str:
    """供 art/code 节点 LLM 使用的纯文本。"""
    if isinstance(doc, str):
        return doc
    parts = [
        f"标题：{doc.get('title', '')}",
        f"玩法：{doc.get('gameplay', '')}",
        f"操作：{doc.get('controls', '')}",
    ]
    levels = doc.get("levels") or []
    if levels:
        parts.append("关卡：" + "、".join(str(x) for x in levels))
    return "\n".join(parts)


def coerce_design_doc(value: dict[str, Any] | str, fallback_title: str) -> dict[str, Any]:
    """检查点/状态中的 design_doc 归一化。"""
    if isinstance(value, dict):
        return normalize_design_doc(value, fallback_title)
    return parse_design_doc(str(value), fallback_title)
