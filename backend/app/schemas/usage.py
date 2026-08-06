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
