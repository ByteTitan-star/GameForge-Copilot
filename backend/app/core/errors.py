from enum import StrEnum

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from app.core.response import ErrorDetail, ErrorResponse

CODE_TO_STATUS: dict[str, int] = {}


class ErrorCode(StrEnum):
    """API 统一错误码枚举，与 HTTP 状态码映射。"""

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
        """构造业务异常。

        作用：携带错误码、用户可见消息与可选结构化 detail。
        场景：业务层校验失败或状态冲突时 raise AppError。
        参数：code - 错误码枚举；message - 对外提示；detail - 附加字段（可选）。
        返回：无。
        """
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)

    @property
    def status_code(self) -> int:
        """将错误码映射为 HTTP 状态码。

        作用：根据 code 查表返回对应 status。
        场景：异常处理器构造 JSONResponse 时读取。
        参数：无。
        返回：HTTP 状态码整数。
        """
        return _CODE_STATUS[self.code]


def _json(code: ErrorCode, message: str, detail: dict | None, status: int) -> JSONResponse:
    """组装统一错误 JSON 响应。

    作用：将错误码、消息与 detail 封装为 ErrorResponse 并返回 JSONResponse。
    场景：各异常处理器内部复用。
    参数：code - 错误码；message - 提示文案；detail - 附加信息；status - HTTP 状态码。
    返回：FastAPI JSONResponse 实例。
    """
    body = ErrorResponse(error=ErrorDetail(code=code.value, message=message, detail=detail))
    return JSONResponse(status_code=status, content=body.model_dump())


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    """处理 AppError 并返回统一错误体。

    作用：把业务异常转为标准 ErrorResponse JSON。
    场景：FastAPI 捕获到 AppError 时自动调用。
    参数：_ - 请求对象（未使用）；exc - 抛出的 AppError。
    返回：带正确状态码的 JSONResponse。
    """
    return _json(exc.code, exc.message, exc.detail, exc.status_code)


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    """处理 Pydantic/FastAPI 入参校验失败。

    作用：将校验错误列表包装为 VALIDATION_ERROR 响应。
    场景：请求体或查询参数校验不通过时由框架调用。
    参数：_ - 请求对象（未使用）；exc - RequestValidationError。
    返回：HTTP 400 的 JSONResponse。
    """
    return _json(
        ErrorCode.VALIDATION_ERROR,
        "入参校验失败",
        {"errors": exc.errors()},
        400,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 注册全局异常处理器。

    作用：绑定 AppError 与 RequestValidationError 的处理函数。
    场景：应用启动装配时调用一次。
    参数：app - FastAPI 应用实例。
    返回：无。
    """
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
