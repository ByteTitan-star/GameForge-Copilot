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
    seq: int | None = None
    payload: dict[str, Any]


class PhaseStartPayload(BaseModel):
    """PhaseStartPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    phase: RunPhase


class LLMCallPayload(BaseModel):
    """LLMCallPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    phase: RunPhase
    model: str
    provider: LLMProvider
    input_tokens: int
    output_tokens: int


class ToolCallPayload(BaseModel):
    """ToolCallPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    phase: RunPhase
    tool: str
    args: dict[str, Any]
    status: str  # "ok" | "error"
    summary: str


class BuildDonePayload(BaseModel):
    """BuildDonePayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    version: int
    artifact_path: str
    preview_url: str
    # ADR-01：三分立；构建成功即可预览，未过 QA 不得 publishable
    generation_success: bool = True
    previewable: bool = True
    publishable: bool = False
    qa_ok: bool = False


class QaReportPayload(BaseModel):
    """QaReportPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    passed: bool
    issues: list[str]
    log_excerpt: str
    console_logs: list[str] = []
    playtest_mode: str = "playwright"
    attempt: int = 1
    failure_kind: str | None = None
    motion_signal: str | None = None


class DesignDoc(BaseModel):
    """策划稿摘要结构（HITL 展示用）。

    场景：hitl_wait 事件 payload。"""

    title: str
    gameplay: str
    controls: str
    levels: list[dict[str, Any]]


class HitlWaitPayload(BaseModel):
    """HitlWaitPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    node: str
    design_doc: DesignDoc
    action_url: str


class UsagePayload(BaseModel):
    """UsagePayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    today_used: int
    daily_limit: int
    remaining: int


class DonePayload(BaseModel):
    """DonePayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    run_id: uuid.UUID
    game_id: uuid.UUID
    version: int
    preview_url: str
    generation_success: bool = True
    previewable: bool = True
    publishable: bool = True
    qa_ok: bool = True


class ErrorPayload(BaseModel):
    """ErrorPayload WebSocket 事件 payload。

    场景：WSEvent.payload 按 type 解析。"""

    code: str
    message: str
    fatal: bool
