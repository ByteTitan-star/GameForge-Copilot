"""美术方向并行生成：A/B 各一次 LLM，再聚合。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.forge.art_direction import merge_parallel_art_options, parse_single_art_option

CompleteFn = Callable[[str, str], Awaitable[str]]

_DIVERSITY = {
    "A": "侧重「材料 / 构图 / 色块结构」形成可辨识视觉语言",
    "B": "侧重「动效语法 / 反馈节奏 / 转场」并与另一方案明显不同",
}


def single_art_option_system(base_prompt: str, *, option_id: str) -> str:
    """在共用 base prompt 上追加单方案约束（并行用）。"""
    oid = option_id.strip().upper()
    axis = _DIVERSITY.get(oid, "")
    recommended = "true" if oid == "A" else "false"
    return (
        f"{base_prompt}\n\n"
        f"【并行单方案任务 TARGET={oid}】只生成方案 {oid}。"
        f"{axis}。"
        "不要输出另一个方案，不要输出 options 数组。"
        "只输出一个合法 JSON 对象，字段为 id/name/summary/recommended；"
        f'id 必须为 "{oid}"，recommended 设为 {recommended}。'
        "最终以聚合规则校正推荐标记。"
    )


async def generate_art_options_parallel(
    *,
    system_prompt: str,
    user_msg: str,
    complete: CompleteFn,
) -> dict[str, list[dict[str, Any]]]:
    """asyncio.gather 并行拉 A/B，再 merge。"""

    async def _one(option_id: str) -> dict[str, Any]:
        system = single_art_option_system(system_prompt, option_id=option_id)
        raw = await complete(system, user_msg)
        return parse_single_art_option(raw, expected_id=option_id)

    opt_a, opt_b = await asyncio.gather(_one("A"), _one("B"))
    return merge_parallel_art_options(opt_a, opt_b)
