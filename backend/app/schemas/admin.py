import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.enums import GameStatus, Role


class AdminUserItem(BaseModel):
    user_id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
    disabled: bool
    created_at: datetime
    daily_token_limit: int | None = None  # 用户级覆盖；null=走全局默认


class AdminUserPatch(BaseModel):
    role: Role | None = None
    disabled: bool | None = None
    daily_token_limit: int | None = None  # 用户级配额覆盖；显式 null 清覆盖


class AdminSettings(BaseModel):
    default_daily_token_limit: int
    default_monthly_token_limit: int = 10_000_000
    default_rate_limit_per_min: int
    admin_contact_email: str = ""


class AuditLogItem(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    target: str | None
    detail: dict[str, Any] | None
    created_at: datetime


class AdminGameSchedulePatch(BaseModel):
    scheduled_take_down_at: datetime | None = None
    scheduled_publish_at: datetime | None = None


class AdminGameItem(BaseModel):
    game_id: uuid.UUID
    title: str
    status: GameStatus
    slug: str | None
    owner_id: uuid.UUID
    current_version: int
    updated_at: datetime
