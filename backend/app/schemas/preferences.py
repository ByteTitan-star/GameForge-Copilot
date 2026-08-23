"""偏好 API schemas。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PreferenceItem(BaseModel):
    """PreferenceItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    id: uuid.UUID
    category: str
    key: str
    value_json: dict[str, Any]
    source: str
    confidence: float
    status: str
    updated_at: datetime | None = None


class PreferenceUpsert(BaseModel):
    """PreferenceUpsert 数据传输对象。

    场景：API 或内部序列化契约。"""

    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=64)
    value_json: dict[str, Any]
    status: str = Field(default="active", max_length=16)


class PreferenceList(BaseModel):
    """PreferenceList 数据传输对象。

    场景：API 或内部序列化契约。"""

    items: list[PreferenceItem]
