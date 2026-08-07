import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import RunPhase, RunStatus


class RunCreate(BaseModel):
    requirement: str
    llm_config_id: uuid.UUID | None = None


class RunResp(BaseModel):
    run_id: uuid.UUID
    game_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    ws_url: str


class RunListItem(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    started_at: datetime
    ended_at: datetime | None = None


class HitlState(BaseModel):
    node: str


class RunStatusResp(BaseModel):
    run_id: uuid.UUID
    game_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    ws_url: str
    current_hitl: HitlState | None = None


class HitlResolveReq(BaseModel):
    node: str
    decision: str  # "approve" | "modify"
    modify_text: str | None = None


class HitlResolveResp(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase


class RunControlResp(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
