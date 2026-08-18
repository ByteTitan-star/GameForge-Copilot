from enum import StrEnum

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.core.response import ErrorDetail, ErrorResponse

CODE_TO_STATUS: dict[str, int] = {}


class ErrorCode(StrEnum):
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    EMAIL_NOT_VERIFIED = "EMAIL_NOT_VERIFIED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    LLM_CONFIG_INVALID = "LLM_CONFIG_INVALID"
    LLM_CONFIG_NOT_FOUND = "LLM_CONFIG_NOT_FOUND"
    LLM_CIRCUIT_OPEN = "LLM_CIRCUIT_OPEN"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    INVALID_STATE = "INVALID_STATE"
    STALE_DECISION = "STALE_DECISION"
    SANDBOX_FAILED = "SANDBOX_FAILED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    HANDLE_TAKEN = "HANDLE_TAKEN"
    PROMOTION_REJECTED_STALE_ARTIFACT = "PROMOTION_REJECTED_STALE_ARTIFACT"


_CODE_STATUS = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.EMAIL_NOT_VERIFIED: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXCEEDED: 429,
    ErrorCode.LLM_CONFIG_INVALID: 400,
    ErrorCode.LLM_CONFIG_NOT_FOUND: 404,
    ErrorCode.LLM_CIRCUIT_OPEN: 503,
    ErrorCode.GAME_NOT_FOUND: 404,
    ErrorCode.INVALID_STATE: 409,
    ErrorCode.STALE_DECISION: 409,
    ErrorCode.SANDBOX_FAILED: 500,
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.EMAIL_TAKEN: 409,
    ErrorCode.HANDLE_TAKEN: 409,
    ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT: 409,
}
CODE_TO_STATUS = {c.value: s for c, s in _CODE_STATUS.items()}


class AppError(Exception):
    """业务异常，由 handler 统一转成 ErrorResponse。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: dict | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)

    @property
    def status_code(self) -> int:
        return _CODE_STATUS[self.code]


def _json(code: ErrorCode, message: str, detail: dict | None, status: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code.value, message=message, detail=detail))
    return JSONResponse(status_code=status, content=body.model_dump())


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return _json(exc.code, exc.message, exc.detail, exc.status_code)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _json(
        ErrorCode.VALIDATION_ERROR,
        "入参校验失败",
        {"errors": exc.errors()},
        400,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
