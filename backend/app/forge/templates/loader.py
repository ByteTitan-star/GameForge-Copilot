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
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def list_templates(*, verified_only: bool = True) -> list[dict[str, Any]]:
    rows = _load()
    if verified_only:
        rows = [r for r in rows if r.get("verified")]
    return rows


def get_template(template_id: str) -> dict[str, Any]:
    for row in _load():
        if row["template_id"] == template_id:
            if not row.get("verified"):
                raise AppError(ErrorCode.VALIDATION_ERROR, f"模板未验证: {template_id}")
            return row
    raise AppError(ErrorCode.VALIDATION_ERROR, f"未知模板: {template_id}")


def reference_artifact_path(template_id: str) -> Path:
    tpl = get_template(template_id)
    rel = tpl.get("reference_artifact")
    if not rel:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"模板缺少 reference_artifact: {template_id}")
    path = (_TEMPLATES_ROOT / str(rel)).resolve()
    if not path.is_file():
        raise AppError(ErrorCode.VALIDATION_ERROR, f"模板产物不存在: {template_id}")
    return path
