import uuid

from pydantic import BaseModel


class UsageBucket(BaseModel):
    """UsageBucket 数据传输对象。

    场景：API 或内部序列化契约。"""

    input_tokens: int
    output_tokens: int
    calls: int


class QuotaInfo(BaseModel):
    """QuotaInfo 数据传输对象。

    场景：API 或内部序列化契约。"""

    daily_token_limit: int
    daily_used: int
    remaining: int


class UsageResp(BaseModel):
    """UsageResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    today: UsageBucket
    month: UsageBucket
    total: UsageBucket
    quota: QuotaInfo


class SystemUsage(BaseModel):
    """SystemUsage 数据传输对象。

    场景：API 或内部序列化契约。"""

    today: UsageBucket
    month: UsageBucket
    total: UsageBucket


class AdminUserUsage(BaseModel):
    """AdminUserUsage 数据传输对象。

    场景：API 或内部序列化契约。"""

    user_id: uuid.UUID
    email: str
    month_input_tokens: int
    month_output_tokens: int
    calls: int


class AdminUsageResp(BaseModel):
    """AdminUsageResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    system: SystemUsage
    top_users: list[AdminUserUsage]


class UsageBreakdownItem(BaseModel):
    """UsageBreakdownItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    id: uuid.UUID
    title: str | None = None
    input_tokens: int
    output_tokens: int
    calls: int
    estimated_usd: float


class GameUsageResp(BaseModel):
    """GameUsageResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    month: UsageBucket
    estimated_usd: float


class GameAnalyticsResp(BaseModel):
    """GameAnalyticsResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    game_id: uuid.UUID
    play_count: int
    pv_30d: int
    uv_30d: int


class AnalyticsTopItem(BaseModel):
    """AnalyticsTopItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    game_id: uuid.UUID
    title: str
    slug: str | None = None
    play_count: int


class AnalyticsTrendPoint(BaseModel):
    """AnalyticsTrendPoint 数据传输对象。

    场景：API 或内部序列化契约。"""

    date: str  # YYYY-MM-DD
    page_views: int
    unique_visitors: int


class AdminAnalyticsResp(BaseModel):
    """AdminAnalyticsResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    top_games: list[AnalyticsTopItem]
    trend: list[AnalyticsTrendPoint]
