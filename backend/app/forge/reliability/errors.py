"""Forge 运行时错误分类（P0）。

RecoverableError 不得直接把 Run 打成 FAILED；仅 FatalError（及明确取消）可进不可恢复终态。
"""

from __future__ import annotations

import re

import httpx


class ForgeRuntimeError(Exception):
    """Forge 运行时错误基类。"""

    error_code: str = "forge_runtime_error"

    def __init__(self, message: str = "", *, cause: BaseException | None = None) -> None:
        """构造 Forge 运行时错误。

        场景：classify_exception 或节点显式抛出。
        参数：message、cause - 原始异常链。
        返回：无。
        """
        super().__init__(message or self.error_code)
        self.cause = cause


class RecoverableError(ForgeRuntimeError):
    """可恢复：retry / fallback / paused+recoverable_error。"""

    error_code = "recoverable_error"


class ProviderTimeout(RecoverableError):
    error_code = "provider_timeout"


class ProviderRateLimit(RecoverableError):
    error_code = "provider_rate_limit"


class Provider5xx(RecoverableError):
    error_code = "provider_5xx"


class InvalidModelOutput(RecoverableError):
    error_code = "invalid_model_output"


class SandboxTimeout(RecoverableError):
    error_code = "sandbox_timeout"


class SandboxOOM(RecoverableError):
    error_code = "sandbox_oom"


class WorkerInterrupted(RecoverableError):
    error_code = "worker_interrupted"


class UserActionRequired(ForgeRuntimeError):
    """需用户介入（HITL），非 fatal、也非自动 retry 语义。"""

    error_code = "user_action_required"


class FatalError(ForgeRuntimeError):
    """不可恢复：数据损坏 / invariant / 安全。"""

    error_code = "fatal_error"


class DataCorruption(FatalError):
    error_code = "data_corruption"


class InvariantViolation(FatalError):
    error_code = "invariant_violation"


class SecurityViolation(FatalError):
    error_code = "security_violation"


def is_recoverable(exc: BaseException) -> bool:
    """判断异常是否属于可恢复类（可 retry / pause）。

    场景：runner 错误处理分支。
    参数：exc。
    返回：RecoverableError 子类时为 True。
    """
    return isinstance(exc, RecoverableError)


def is_fatal(exc: BaseException) -> bool:
    """判断异常是否不可恢复（应 FAILED 终态）。

    场景：runner 错误处理分支。
    参数：exc。
    返回：FatalError 子类时为 True。
    """
    return isinstance(exc, FatalError)


def classify_exception(exc: BaseException) -> ForgeRuntimeError:
    """将常见底层异常映射为 Forge 错误分类；已是 Forge 错误则原样返回。"""
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
