import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.enums import LLMProvider, RunPhase, WSEventType


class WSEvent(BaseModel):
    """WS 事件外层；payload 按 type 不同，前端据 type 解析。"""

    type: WSEventType
    run_id: uuid.UUID
    ts: datetime
    payload: dict[str, Any]


class PhaseStartPayload(BaseModel):
    phase: RunPhase


class LLMCallPayload(BaseModel):
    phase: RunPhase
    model: str
    provider: LLMProvider
    input_tokens: int
    output_tokens: int


class ToolCallPayload(BaseModel):
    phase: RunPhase
    tool: str
    args: dict[str, Any]
    status: str  # "ok" | "error"
    summary: str


class BuildDonePayload(BaseModel):
    version: int
    artifact_path: str
    preview_url: str


class QaReportPayload(BaseModel):
    passed: bool
    issues: list[str]
    log_excerpt: str


class DesignDoc(BaseModel):
    title: str
    gameplay: str
    controls: str
    levels: list[dict[str, Any]]


class HitlWaitPayload(BaseModel):
    node: str
    design_doc: DesignDoc
    action_url: str


class UsagePayload(BaseModel):
    today_used: int
    daily_limit: int
    remaining: int


class DonePayload(BaseModel):
    run_id: uuid.UUID
    game_id: uuid.UUID
    version: int
    preview_url: str


class ErrorPayload(BaseModel):
    code: str
    message: str
    fatal: bool
