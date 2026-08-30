"""Forge 运行时错误分类（P0）。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
把「底层异常」统一映射成 Forge 语义，供 graph.run_generation 外层 catch 决策：

  RecoverableError  → 可 pause / retry，不得直接把 Run 打成 FAILED
  UserActionRequired → 等人（HITL），不是自动 retry，也不是 fatal
  FatalError        → 不可恢复（数据损坏 / invariant / 安全），可进终态

调用链常见落点：
  graph.py run_generation except 块
    → classify_exception(e) / is_recoverable / is_fatal
    → _pause_recoverable 或 _fail

设计依据：ADR-05（可恢复暂停）+ 可靠性 P0。
"""

from __future__ import annotations

import re

import httpx


class ForgeRuntimeError(Exception):
    """Forge 运行时错误基类；带稳定 error_code，便于日志与 FailureReport。"""

    error_code: str = "forge_runtime_error"

    def __init__(self, message: str = "", *, cause: BaseException | None = None) -> None:
        super().__init__(message or self.error_code)
        self.cause = cause


class RecoverableError(ForgeRuntimeError):
    """可恢复：节点 retry / 降级 / paused+recoverable_error。

    注意：可恢复 ≠ 用户 HITL。HITL 用 UserActionRequired 或 pause_reason=hitl。
    """

    error_code = "recoverable_error"


class ProviderTimeout(RecoverableError):
    """LLM / HTTP 提供商超时。"""

    error_code = "provider_timeout"


class ProviderRateLimit(RecoverableError):
    """提供商 429 限流。"""

    error_code = "provider_rate_limit"


class Provider5xx(RecoverableError):
    """提供商 5xx。"""

    error_code = "provider_5xx"


class InvalidModelOutput(RecoverableError):
    """模型输出无法解析 / 校验失败（可再试或回退）。"""

    error_code = "invalid_model_output"


class SandboxTimeout(RecoverableError):
    """沙箱构建 / 执行超时。"""

    error_code = "sandbox_timeout"


class SandboxOOM(RecoverableError):
    """沙箱内存不足。"""

    error_code = "sandbox_oom"


class WorkerInterrupted(RecoverableError):
    """Worker 中断 / 未知瞬态；默认兜底成可恢复，避免误杀整个 Run。"""

    error_code = "worker_interrupted"


class UserActionRequired(ForgeRuntimeError):
    """需用户介入（HITL），非 fatal、也非自动 retry 语义。"""

    error_code = "user_action_required"


class FatalError(ForgeRuntimeError):
    """不可恢复：数据损坏 / invariant / 安全。仅 Fatal（及明确取消）可进 FAILED 终态。"""

    error_code = "fatal_error"


class DataCorruption(FatalError):
    error_code = "data_corruption"


class InvariantViolation(FatalError):
    error_code = "invariant_violation"


class SecurityViolation(FatalError):
    """【安全第 6 步】安全策略违例：Fatal，不可自动 retry。"""

    error_code = "security_violation"


def is_recoverable(exc: BaseException) -> bool:
    """是否属于可自动恢复 / 可 pause 的错误族。"""
    return isinstance(exc, RecoverableError)


def is_fatal(exc: BaseException) -> bool:
    """是否属于不可恢复致命错误。"""
    return isinstance(exc, FatalError)


def classify_exception(exc: BaseException) -> ForgeRuntimeError:
    """将常见底层异常映射为 Forge 错误分类；已是 Forge 错误则原样返回。

    映射规则（简化）：
    - httpx 超时 / TimeoutError → ProviderTimeout
    - HTTP 429 → ProviderRateLimit；5xx → Provider5xx
    - 文案含 OOM → SandboxOOM；含 sandbox timeout → SandboxTimeout
    - 其余未知 → WorkerInterrupted（偏可恢复，真正 invariant 应由调用方显式抛 Fatal）
    """
    if isinstance(exc, ForgeRuntimeError):
        return exc

    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return ProviderTimeout(str(exc) or "provider timeout", cause=exc)

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return ProviderRateLimit(str(exc) or "rate limited", cause=exc)
        if 500 <= status <= 599:
            return Provider5xx(str(exc) or f"provider {status}", cause=exc)
        return WorkerInterrupted(str(exc) or f"http {status}", cause=exc)

    msg = str(exc).lower()
    if "out of memory" in msg or re.search(r"\boom\b", msg):
        return SandboxOOM(str(exc) or "sandbox oom", cause=exc)
    if "构建超时" in str(exc) or "sandbox timeout" in msg:
        return SandboxTimeout(str(exc) or "sandbox timeout", cause=exc)

    # 未知瞬态默认按可恢复中断，避免误杀整个 Run；真正 invariant 应由调用方显式抛 Fatal。
    return WorkerInterrupted(str(exc) or "worker interrupted", cause=exc)
