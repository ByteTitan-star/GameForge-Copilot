"""内置游戏起点模板（B5）。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.errors import AppError, ErrorCode

_CATALOG = Path(__file__).with_name("catalog.json")


@lru_cache(maxsize=1)
def _load() -> list[dict[str, Any]]:
    return json.loads(_CATALOG.read_text(encoding="utf-8"))


def list_templates() -> list[dict[str, Any]]:
    return _load()


def get_template(template_id: str) -> dict[str, Any]:
    for row in _load():
        if row["template_id"] == template_id:
            return row
    raise AppError(ErrorCode.VALIDATION_ERROR, f"未知模板: {template_id}")
