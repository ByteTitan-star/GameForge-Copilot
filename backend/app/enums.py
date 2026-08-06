from enum import Enum


class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"


class GameStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    REJECTED = "rejected"
    TAKEN_DOWN = "taken_down"


class RunStatus(str, Enum):
    RUNNING = "running"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class RunPhase(str, Enum):
    PLAN = "plan"
    ART = "art"
    CODE = "code"
    QA = "qa"
    DONE = "done"


class PublishStatus(str, Enum):
    SUBMITTED = "submitted"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


class LLMProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENAI_COMPAT = "openai_compat"


class WSEventType(str, Enum):
    PHASE_START = "phase_start"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    BUILD_DONE = "build_done"
    QA_REPORT = "qa_report"
    HITL_WAIT = "hitl_wait"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"
