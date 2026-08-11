import uuid

from pydantic import BaseModel


class UsageBucket(BaseModel):
    input_tokens: int
    output_tokens: int
    calls: int


class QuotaInfo(BaseModel):
    daily_token_limit: int
    daily_used: int
    remaining: int


class UsageResp(BaseModel):
    today: UsageBucket
    month: UsageBucket
    total: UsageBucket
    quota: QuotaInfo


class SystemUsage(BaseModel):
    today: UsageBucket
    month: UsageBucket
    total: UsageBucket


class AdminUserUsage(BaseModel):
    user_id: uuid.UUID
    email: str
    month_input_tokens: int
    month_output_tokens: int
    calls: int


class AdminUsageResp(BaseModel):
    system: SystemUsage
    top_users: list[AdminUserUsage]


class UsageBreakdownItem(BaseModel):
    id: uuid.UUID
    title: str | None = None
    input_tokens: int
    output_tokens: int
    calls: int
    estimated_usd: float


class GameUsageResp(BaseModel):
    game_id: uuid.UUID
    month: UsageBucket
    estimated_usd: float


class GameAnalyticsResp(BaseModel):
    game_id: uuid.UUID
    play_count: int
    pv_30d: int
    uv_30d: int


class AnalyticsTopItem(BaseModel):
    game_id: uuid.UUID
    title: str
    slug: str | None = None
    play_count: int


class AnalyticsTrendPoint(BaseModel):
    date: str  # YYYY-MM-DD
    page_views: int
    unique_visitors: int


class AdminAnalyticsResp(BaseModel):
    top_games: list[AnalyticsTopItem]
    trend: list[AnalyticsTrendPoint]
