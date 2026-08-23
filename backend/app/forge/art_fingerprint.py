"""P6 Art dependency fingerprint：NFC + canonical JSON + 版本门控。"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any

FINGERPRINT_VERSION = "art-dependency-fingerprint-v1"


def _nfc(value: Any) -> Any:
    """递归对字符串做 NFC 归一化，供指纹序列化使用。"""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _nfc(item) for key, item in value.items()}
    return unicodedata.normalize("NFC", str(value))


def canonical_dumps(value: Any) -> str:
    """将值序列化为稳定 JSON 字符串（sort_keys、无 NaN）。"""
    return json.dumps(
        _nfc(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def art_dependency_projection(design_doc: dict[str, Any] | None) -> dict[str, Any]:
    """从策划稿抽取影响美术复用的字段子集（素材、配色、实体、UI 等）。"""
    doc = design_doc if isinstance(design_doc, dict) else {}
    raw_presentation = doc.get("presentation")
    raw_ui = doc.get("ui")
    raw_entities = doc.get("entities")
    presentation: dict[str, Any] = raw_presentation if isinstance(raw_presentation, dict) else {}
    ui: dict[str, Any] = raw_ui if isinstance(raw_ui, dict) else {}
    entities: list[Any] = raw_entities if isinstance(raw_entities, list) else []
    return {
        "asset_needs": presentation.get("asset_needs") or [],
        "color_palette": presentation.get("color_palette") or [],
        "effects": presentation.get("effects") or [],
        "entities": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "type": item.get("type"),
            }
            for item in entities
            if isinstance(item, dict)
        ],
        "ui_screens": ui.get("screens") or [],
        "visual_style": presentation.get("visual_style") or "",
    }


def art_dependency_fingerprint(
    design_doc: dict[str, Any] | None,
    *,
    version: str = FINGERPRINT_VERSION,
) -> tuple[str, str]:
    """计算美术依赖投影的 SHA-256 指纹与版本标签。"""
    blob = canonical_dumps(art_dependency_projection(design_doc))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return digest, version


def can_reuse_art(
    *,
    stored_fp: str | None,
    stored_version: str | None,
    new_fp: str | None,
    new_version: str | None,
) -> bool:
    """判断策划变更后是否可复用已有美术 revision（版本与指纹均须匹配）。"""
    if not stored_fp or not stored_version or not new_fp or not new_version:
        return False
    if stored_version != new_version:
        return False
    return stored_fp == new_fp
