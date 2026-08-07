"""Development-only helpers (verification peek for smoke / local QA)."""

from fastapi import APIRouter, Query

from app.auth.deps import RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse

router = APIRouter(prefix="/dev", tags=["dev"])


@router.get("/verification-code")
async def peek_verification_code(
    r: RedisClient,
    email: str = Query(..., min_length=3),
) -> ApiResponse[dict[str, str]]:
    if settings.env != "development":
        raise AppError(ErrorCode.FORBIDDEN, "dev endpoint disabled")
    key = f"dev:verify:{email.strip().lower()}"
    code = await r.get(key)
    if not code:
        raise AppError(ErrorCode.VALIDATION_ERROR, "no pending verification code for this email")
    return ApiResponse(data={"code": str(code)})
