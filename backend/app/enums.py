from enum import StrEnum


class Role(StrEnum):
    """用户角色：普通用户与管理员。"""

    USER = "user"
    ADMIN = "admin"


class GameStatus(StrEnum):
    """游戏生命周期状态（草稿至上下架）。"""

    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    REJECTED = "rejected"
    TAKEN_DOWN = "taken_down"


class RunStatus(StrEnum):
    """Forge 运行会话的顶层状态。"""

    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class PauseReason(StrEnum):
    """Run 处于 paused 时的细分原因（ADR-05：不新增 RunStatus）。"""

    WAITING_USER = "waiting_user"
    RECOVERABLE_ERROR = "recoverable_error"
    QUOTA_BLOCKED = "quota_blocked"
    MANUAL_HOLD = "manual_hold"


class RunPhase(StrEnum):
    """Forge 流水线当前阶段。"""

    PLAN = "plan"
    ART = "art"
    CODE = "code"
    QA = "qa"
    DONE = "done"


class RunCommandType(StrEnum):
    """用户对运行会话下发的 HITL 指令类型。"""

    APPROVE_PLAN = "approve_plan"
    REVISE_PLAN = "revise_plan"
    SELECT_ART_A = "select_art_a"
    SELECT_ART_B = "select_art_b"
    REVISE_ART = "revise_art"
    RETRY_IMPLEMENTATION = "retry_implementation"
    RETRY_INFRA = "retry_infra"
    CANCEL_RUN = "cancel_run"


class RunCommandStatus(StrEnum):
    """单条运行指令的执行状态。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FailureClass(StrEnum):
    """失败报告的分类，用于恢复策略与指标。"""

    INFRA_TRANSIENT = "infra_transient"
    IMPLEMENTATION_DEFECT = "implementation_defect"
    CAPABILITY_MISMATCH = "capability_mismatch"
    ACCEPTANCE_MISMATCH = "acceptance_mismatch"
    RESOURCE_EXCEEDED = "resource_exceeded"
    POLICY_SECURITY = "policy_security"
    UNKNOWN = "unknown"


class ArtifactKind(StrEnum):
    """运行产物的种类。"""

    PLAN = "plan"
    ART = "art"
    CANDIDATE = "candidate"


class ArtifactStatus(StrEnum):
    """产物是否仍为当前有效版本。"""

    ACTIVE = "active"
    STALE = "stale"


class EntryPhase(StrEnum):
    """用户进入 Forge 时的起始阶段。"""

    PLAN = "plan"
    CODE = "code"
    CHAT = "chat"


class ReactionType(StrEnum):
    """用户对游戏的互动类型。"""

    LIKE = "like"
    FAVORITE = "favorite"


class PublishStatus(StrEnum):
    """游戏提审与发布审核状态。"""

    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class LLMProvider(StrEnum):
    """平台支持的 LLM 供应商标识。"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPAT = "openai_compat"


class WSEventType(StrEnum):
    """Forge 运行 WebSocket 推送的事件类型。"""

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
