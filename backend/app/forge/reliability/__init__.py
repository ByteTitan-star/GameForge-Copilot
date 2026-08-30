"""Forge 可靠性子系统（P0）：错误分类、暂停原因、节点策略、幂等。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
本包是 LangGraph 节点「跑多久 / 挂了怎么办 / 副作用别重做」的公共层：

  policy.py      — 各节点 TimeoutPolicy / RetryPolicy（数字权威）
  errors.py      — Recoverable vs Fatal 异常分类
  pause.py       — paused + pause_reason + recovery checkpoint
  idempotency.py — promote / billing 等副作用 Redis 幂等
  artifact_gate.py — previewable / publishable 门禁（ADR-01）

主图 graph.py 通过本包的 re-export 使用上述能力。
"""

from app.forge.reliability.artifact_gate import ArtifactGate, derive_artifact_gate
from app.forge.reliability.errors import (
    DataCorruption,
    FatalError,
    ForgeRuntimeError,
    InvalidModelOutput,
    InvariantViolation,
    Provider5xx,
    ProviderRateLimit,
    ProviderTimeout,
    RecoverableError,
    SandboxOOM,
    SandboxTimeout,
    SecurityViolation,
    UserActionRequired,
    WorkerInterrupted,
    classify_exception,
    is_fatal,
    is_recoverable,
)
from app.forge.reliability.idempotency import (
    already_applied,
    get_side_effect_value,
    side_effect_key,
    try_begin_side_effect,
)
from app.forge.reliability.pause import (
    RecoveryInfo,
    apply_paused_metadata,
    build_pause_checkpoint,
    merge_pause_checkpoint,
    pause_reason_from_state,
    recovery_from_state,
)
from app.forge.reliability.policy import (
    NODE_EXECUTION_POLICIES,
    langgraph_retry_policy,
    langgraph_timeout_policy,
    resolve_node_run_timeout,
)

__all__ = [
    "ArtifactGate",
    "DataCorruption",
    "FatalError",
    "ForgeRuntimeError",
    "InvalidModelOutput",
    "InvariantViolation",
    "NODE_EXECUTION_POLICIES",
    "Provider5xx",
    "ProviderRateLimit",
    "ProviderTimeout",
    "RecoverableError",
    "RecoveryInfo",
    "SandboxOOM",
    "SandboxTimeout",
    "SecurityViolation",
    "UserActionRequired",
    "WorkerInterrupted",
    "already_applied",
    "apply_paused_metadata",
    "build_pause_checkpoint",
    "classify_exception",
    "derive_artifact_gate",
    "get_side_effect_value",
    "is_fatal",
    "is_recoverable",
    "langgraph_retry_policy",
    "langgraph_timeout_policy",
    "merge_pause_checkpoint",
    "pause_reason_from_state",
    "recovery_from_state",
    "resolve_node_run_timeout",
    "side_effect_key",
    "try_begin_side_effect",
]
