import re
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

_HANDLE_RE = re.compile(r"^[a-z0-9_]{3,32}$")


class ProfilePatch(BaseModel):
    """ProfilePatch 数据传输对象。

    场景：API 或内部序列化契约。"""

    handle: str | None = None
    display_name: str | None = None
    profile_public: bool | None = None

    @field_validator("handle")
    @classmethod
    def validate_handle(cls, v: str | None) -> str | None:
        """校验创作者 handle：3–32 位小写字母、数字或下划线。

        场景：ProfilePatch 入参校验。
        参数：v - 原始 handle。
        返回：规范化后的 handle 或 None。
        """
        if v is None:
            return v
        h = v.strip().lower()
        if not _HANDLE_RE.match(h):
            raise ValueError("handle 须为 3–32 位小写字母、数字或下划线")
        return h

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str | None) -> str | None:
        """校验展示名非空且不超过 64 字符。

        场景：ProfilePatch 入参校验。
        参数：v - 原始 display_name。
        返回：strip 后的名称或 None。
        """
        if v is None:
            return v
        name = v.strip()
        if not name:
            raise ValueError("display_name 不能为空")
        if len(name) > 64:
            raise ValueError("display_name 最长 64 字符")
        return name


class UserProfile(BaseModel):
    """UserProfile 数据传输对象。

    场景：API 或内部序列化契约。"""

    user_id: uuid.UUID
    email: str
    handle: str | None = None
    display_name: str | None = None
    profile_public: bool = True


class CreatorGameItem(BaseModel):
    """CreatorGameItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    slug: str
    play_count: int
    published_at: datetime | None


class CreatorProfile(BaseModel):
    """CreatorProfile 数据传输对象。

    场景：API 或内部序列化契约。"""

    handle: str
    display_name: str | None
    total_plays: int
    latest_published_at: datetime | None
    games: list[CreatorGameItem]
