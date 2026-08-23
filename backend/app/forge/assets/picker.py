"""Built-in CC0 asset manifest picker for art subgraph (B9)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass
class PickedAsset:
    asset_id: str
    filename: str
    kind: str
    description: str
    data_uri: str
    hosting_path: str | None = None


_MANIFEST = Path(__file__).with_name("manifest.json")


@lru_cache(maxsize=1)
def _load_manifest() -> list[dict[str, Any]]:
    """加载内置 CC0 素材 manifest.json（lru_cache）。

    场景：asset_pick 关键词匹配选素材。
    参数：无。
    返回：素材行 dict 列表。
    """
    return json.loads(_MANIFEST.read_text(encoding="utf-8"))


def asset_pick(design_doc: str) -> list[PickedAsset]:
    """按设计稿关键词从内置 manifest 挑选素材。

    场景：art 子图注入 data URI 素材到 prompt。
    参数：design_doc - 策划文本（用于 tag 匹配）。
    返回：最多 6 个 PickedAsset。
    """
    text = design_doc.lower()
    picked: list[PickedAsset] = []
    for row in _load_manifest():
        tags = [t.lower() for t in row.get("tags", [])]
        score = sum(1 for t in tags if t in text)
        if score > 0 or row.get("kind") == "sprite" and len(picked) < 2:
            picked.append(
                PickedAsset(
                    asset_id=row["asset_id"],
                    filename=row["filename"],
                    kind=row["kind"],
                    description=row["description"],
                    data_uri=row["data_uri"],
                )
            )
    if not picked:
        # 默认至少给 player + bg
        for row in _load_manifest()[:2]:
            picked.append(
                PickedAsset(
                    asset_id=row["asset_id"],
                    filename=row["filename"],
                    kind=row["kind"],
                    description=row["description"],
                    data_uri=row["data_uri"],
                )
            )
    return picked[:6]


def format_assets_for_prompt(assets: list[PickedAsset]) -> str:
    """将选中素材格式化为 LLM prompt 附录文本。

    场景：execute_code_or_repair 拼接 assets_block。
    参数：assets - PickedAsset 列表。
    返回：多行说明字符串。
    """
    lines = ["可用素材（请在 HTML 内联引用 data URI 或注释标注文件名）："]
    for a in assets:
        lines.append(f"- {a.asset_id} ({a.kind}): {a.filename} — {a.description}")
        lines.append(f"  data_uri: {a.data_uri[:80]}...")
    return "\n".join(lines)
