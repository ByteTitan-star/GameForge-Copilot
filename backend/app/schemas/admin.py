import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.enums import GameStatus, Role


class AdminUserItem(BaseModel):
    """AdminUserItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    user_id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
    disabled: bool
    created_at: datetime
    daily_token_limit: int | None = None  # 用户级覆盖；null=走全局默认


class AdminUserPatch(BaseModel):
    """AdminUserPatch 数据传输对象。

    场景：API 或内部序列化契约。"""

    role: Role | None = None
    disabled: bool | None = None
    daily_token_limit: int | None = None  # 用户级配额覆盖；显式 null 清覆盖


class AdminAuditLlmSettings(BaseModel):
    """平台预设审核模型（护栏）配置。GET 回 masked apikey；PUT 收明文（空/masked=保留旧值）。"""

    enabled: bool = True
    provider: str = "openai_compat"
    model: str = ""
    apikey: str = ""
    base_url: str = ""


class AdminSettings(BaseModel):
    """AdminSettings 数据传输对象。

    场景：API 或内部序列化契约。"""

    default_daily_token_limit: int
    default_monthly_token_limit: int = 10_000_000
    default_rate_limit_per_min: int
    admin_contact_email: str = ""
    audit_llm: AdminAuditLlmSettings | None = None


class AdminAuditLlmTestResp(BaseModel):
    """AdminAuditLlmTestResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    tested_ok: bool
    error: str | None = None


class AuditLogItem(BaseModel):
    """AuditLogItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    target: str | None
    detail: dict[str, Any] | None
    created_at: datetime


class AdminGameFeaturedPatch(BaseModel):
    """AdminGameFeaturedPatch 数据传输对象。

    场景：API 或内部序列化契约。"""

    featured_rank: int | None = None


class AdminGameSchedulePatch(BaseModel):
    """AdminGameSchedulePatch 数据传输对象。

    场景：API 或内部序列化契约。"""

    scheduled_take_down_at: datetime | None = None
    scheduled_publish_at: datetime | None = None


class AdminGameItem(BaseModel):
    """AdminGameItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    status: GameStatus
    slug: str | None
    owner_id: uuid.UUID
    current_version: int
    updated_at: datetime
    featured: bool = False  # 由 featured_rank is not None 派生，供后台精选开关反映状态
