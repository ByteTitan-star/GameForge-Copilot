from enum import StrEnum


class Role(StrEnum):
    USER = "user"
    ADMIN = "admin"


class GameStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    REJECTED = "rejected"
    TAKEN_DOWN = "taken_down"


class RunStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class PauseReason(StrEnum):
    """paused 细分原因（ADR-05：不新增 RunStatus）。"""

    WAITING_USER = "waiting_user"
    RECOVERABLE_ERROR = "recoverable_error"
    QUOTA_BLOCKED = "quota_blocked"
    MANUAL_HOLD = "manual_hold"


class RunPhase(StrEnum):
    PLAN = "plan"
    ART = "art"
    CODE = "code"
    QA = "qa"
    DONE = "done"


class RunCommandType(StrEnum):
    APPROVE_PLAN = "approve_plan"
    REVISE_PLAN = "revise_plan"
    SELECT_ART_A = "select_art_a"
    SELECT_ART_B = "select_art_b"
    REVISE_ART = "revise_art"
    RETRY_IMPLEMENTATION = "retry_implementation"
    RETRY_INFRA = "retry_infra"
    CANCEL_RUN = "cancel_run"


class RunCommandStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureClass(StrEnum):
    INFRA_TRANSIENT = "infra_transient"
    IMPLEMENTATION_DEFECT = "implementation_defect"
    CAPABILITY_MISMATCH = "capability_mismatch"
    ACCEPTANCE_MISMATCH = "acceptance_mismatch"
    RESOURCE_EXCEEDED = "resource_exceeded"
    POLICY_SECURITY = "policy_security"
    UNKNOWN = "unknown"


class ArtifactKind(StrEnum):
    PLAN = "plan"
    ART = "art"
    CANDIDATE = "candidate"


class ArtifactStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"


class EntryPhase(StrEnum):
    PLAN = "plan"
    CODE = "code"
    CHAT = "chat"


class ReactionType(StrEnum):
    LIKE = "like"
    FAVORITE = "favorite"


class PublishStatus(StrEnum):
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class LLMProvider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPAT = "openai_compat"


class WSEventType(StrEnum):
    PHASE_START = "phase_start"
    LLM_CALL = "llm_call"
    # LLM 流式微批增量：payload 含 phase + delta（攒 3-5 字一批的打字机文本）
    LLM_DELTA = "llm_delta"
    TOOL_CALL = "tool_call"
    BUILD_DONE = "build_done"
    QA_REPORT = "qa_report"
    HITL_WAIT = "hitl_wait"
    USAGE = "usage"
    DONE = "done"
    # 内容审核命中（输入注入/输出恶意）：前端收到后断 WS + 弹友好提示
    ATTACKED = "attacked"
    ERROR = "error"
