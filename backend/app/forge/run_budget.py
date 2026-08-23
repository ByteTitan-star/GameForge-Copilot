"""单次 Forge Run token 预算：识别与暂停语义。"""

from __future__ import annotations

from app.core.errors import AppError, ErrorCode


def is_forge_run_budget_error(exc: BaseException) -> bool:
    """call_llm 在 run 级预算耗尽时抛出的 QUOTA_EXCEEDED（detail.scope=forge_run）。"""
    if not isinstance(exc, AppError):
        return False
    if exc.code is not ErrorCode.QUOTA_EXCEEDED:
        return False
    detail = exc.detail if isinstance(exc.detail, dict) else {}
    return detail.get("scope") == "forge_run"
