import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.enums import EntryPhase, RunPhase, RunStatus


class RunCreate(BaseModel):
    # max_length 既是输入校验，也是 prompt injection 的防线之一：拒绝超长 jailbreak payload。
    # 非空校验由 services 层 .strip() 兜底，这里不强制 min_length 以兼容最小 input 的测试。
    requirement: str = Field(..., max_length=10000)
    llm_config_id: uuid.UUID | None = None


class RunResp(BaseModel):
    run_id: uuid.UUID
    game_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    entry_phase: EntryPhase
    ws_url: str


class RunListItem(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    started_at: datetime
    ended_at: datetime | None = None


class HitlState(BaseModel):
    node: str


class HitlWaitDetail(BaseModel):
    node: str
    design_doc: dict | str | None = None
    action_url: str | None = None
    art_options: dict | None = None
    allowed_commands: list[str] | None = None
    control_revision: int | None = None
    failure: dict | None = None


class RecoveryDetail(BaseModel):
    node: str
    error_code: str
    attempts: int
    can_retry: bool = True


class ArtifactGateDetail(BaseModel):
    """ADR-01：previewable ≠ publishable，build_ok ≠ qa_ok。"""

    generation_success: bool = False
    previewable: bool = False
    publishable: bool = False
    qa_ok: bool = False


class RunStatusResp(BaseModel):
    run_id: uuid.UUID
    game_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
    entry_phase: EntryPhase
    ws_url: str
    current_hitl: HitlState | None = None
    hitl_wait: HitlWaitDetail | None = None
    pause_reason: str | None = None
    recovery: RecoveryDetail | None = None
    artifact_gate: ArtifactGateDetail | None = None


class HitlResolveReq(BaseModel):
    node: str
    # 兼容旧客户端：decision；P2 起优先使用 command（RunCommandType）。
    decision: str | None = None
    command: str | None = None
    modify_text: str | None = Field(default=None, max_length=10000)
    expected_control_revision: int | None = Field(default=None, ge=0)


class HitlResolveResp(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase


class RunControlResp(BaseModel):
    run_id: uuid.UUID
    status: RunStatus
    phase: RunPhase
