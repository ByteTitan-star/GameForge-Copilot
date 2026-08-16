"""偏好 API schemas。"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PreferenceItem(BaseModel):
    id: uuid.UUID
    category: str
    key: str
    value_json: dict[str, Any]
    source: str
    confidence: float
    status: str
    updated_at: datetime | None = None


class PreferenceUpsert(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=64)
    value_json: dict[str, Any]
    status: str = Field(default="active", max_length=16)


class PreferenceList(BaseModel):
    items: list[PreferenceItem]
