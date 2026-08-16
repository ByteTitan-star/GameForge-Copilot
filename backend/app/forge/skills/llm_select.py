"""可选 LLM 自选 Methodology Skill（Policy 永不由 LLM 选择）。"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from app.forge.skills.models import SkillMeta

LlmComplete = Callable[[str, str], Awaitable[str]]

_SELECT_SYSTEM = """
你是 Skill 路由器。只能从给定候选 Methodology 中选择，输出合法 JSON：
{"skill_ids":["id1","id2"]}
规则：最多选 3 个；禁止选择 policy/*；禁止编造未列出的 id；若不确定选最相关的 1–2 个。
""".strip()


async def select_methodology_ids_via_llm(
    *,
    node: str,
    candidates: list[SkillMeta],
    hints: dict[str, Any],
    complete: LlmComplete,
    max_skills: int = 3,
) -> list[str] | None:
    """返回 LLM 选择的 methodology id 列表；失败返回 None（调用方回落确定性路由）。"""
    if not candidates:
        return []
    catalog = [
        {"id": m.id, "name": m.name, "description": m.description}
        for m in candidates
        if m.kind == "methodology"
    ]
    allow = {c["id"] for c in catalog}
    user = (
        f"node={node}\n"
        f"hints={json.dumps(hints, ensure_ascii=False, default=str)[:1200]}\n"
        f"candidates={json.dumps(catalog, ensure_ascii=False)}\n"
        "请输出 skill_ids JSON。"
    )
    try:
        raw = await complete(_SELECT_SYSTEM, user)
        ids = _parse_skill_ids(raw)
    except Exception:  # noqa: BLE001 选路失败必须可回落
        return None
    filtered = [i for i in ids if i in allow][:max_skills]
    # 空列表视为选路失败（常见于 mock/错 prompt 返回其它 JSON），回落确定性路由
    if not filtered:
        return None
    return filtered


def _parse_skill_ids(raw: str) -> list[str]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    if isinstance(data, dict):
        ids = data.get("skill_ids") or data.get("skills") or []
    elif isinstance(data, list):
        ids = data
    else:
        return []
    out: list[str] = []
    for item in ids:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]).strip())
    return out
