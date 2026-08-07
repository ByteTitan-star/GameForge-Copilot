from collections.abc import Sequence
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse[T](BaseModel):
    """统一成功响应：{"data": ...}"""

    data: T


class PaginatedData[T](BaseModel):
    """统一分页响应：{data, total, page, size}"""

    data: Sequence[T]
    total: int
    page: int
    size: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict | None = None


class ErrorResponse(BaseModel):
    """统一错误响应：{"error": {code, message, detail}}"""

    error: ErrorDetail
