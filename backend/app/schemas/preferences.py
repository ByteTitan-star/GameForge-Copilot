"""偏好 API schemas（ADR-16 v2：目录键形态）。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PreferenceItem(BaseModel):
    """目录槽位形态；value 为按槽位类型校验后的标量文本。"""

    id: uuid.UUID
    preference_key: str
    value: str
    value_type: str
    source: str
    confidence: float
    updated_at: datetime | None = None


class PreferenceUpsert(BaseModel):
    """用户显式设置：key 须在目录内（别名自动归一），value 须符合槽位类型。"""

    preference_key: str = Field(min_length=1, max_length=64)
    value: str | bool | int | float = Field(min_length=1, max_length=64)


class PreferenceList(BaseModel):
    items: list[PreferenceItem]


class PreferenceRemoveResult(BaseModel):
    archived: int
