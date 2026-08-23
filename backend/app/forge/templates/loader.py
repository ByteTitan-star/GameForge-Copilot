"""内置游戏起点模板（B-B1 / B5）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.errors import AppError, ErrorCode

_CATALOG = Path(__file__).with_name("catalog.json")
_TEMPLATES_ROOT = Path(__file__).parent


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    """加载 templates/catalog.json（lru_cache）。

    场景：list_templates / get_template。
    参数：无。
    返回：模板元数据 dict 列表。
    """
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def list_templates(*, verified_only: bool = False) -> list[dict[str, Any]]:
    """列出 catalog 模板。公开 API 默认返回全部；reference playtest 等仍可按 verified 过滤。"""
    rows = _load()
    if verified_only:
        rows = [r for r in rows if r.get("verified")]
    return rows


def get_template(template_id: str, *, require_verified: bool = False) -> dict[str, Any]:
    """按 template_id 获取 catalog 中的模板元数据。

    场景：create_game 选模板、reference playtest。
    参数：template_id、require_verified - 是否要求 verified。
    返回：模板 dict；未知 id 抛 VALIDATION_ERROR。
    """
    for row in _load():
        if row["template_id"] == template_id:
            if require_verified and not row.get("verified"):
                raise AppError(ErrorCode.VALIDATION_ERROR, f"模板未验证: {template_id}")
            return row
    raise AppError(ErrorCode.VALIDATION_ERROR, f"未知模板: {template_id}")


def template_play_url(template_id: str) -> str | None:
    """有 reference_artifact 时返回公开试玩路径，否则 None。"""
    row = get_template(template_id)
    if not row.get("reference_artifact"):
        return None
    return f"/play/template/{template_id}"


def reference_artifact_path(template_id: str) -> Path:
    """已验证模板的 reference 产物路径（playtest 用）。"""
    return _resolve_reference_path(template_id, require_verified=True)


def public_reference_path(template_id: str) -> Path:
    """公开试玩用 reference 产物路径（不要求 verified）。"""
    return _resolve_reference_path(template_id, require_verified=False)


def _resolve_reference_path(template_id: str, *, require_verified: bool) -> Path:
    """解析模板 reference_artifact 的本地文件绝对路径。

    场景：reference_artifact_path / public_reference_path。
    参数：template_id、require_verified。
    返回：存在的产物文件 Path。
    """
    tpl = get_template(template_id, require_verified=require_verified)
    rel = tpl.get("reference_artifact")
    if not rel:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"模板缺少 reference_artifact: {template_id}")
    path = (_TEMPLATES_ROOT / str(rel)).resolve()
    if not path.is_file():
        raise AppError(ErrorCode.VALIDATION_ERROR, f"模板产物不存在: {template_id}")
    return path
