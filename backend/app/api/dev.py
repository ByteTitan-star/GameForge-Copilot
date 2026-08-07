"""Development-only helpers (verification peek, Redis/queue debug)."""

from uuid import UUID

from fastapi import APIRouter, Query

from app.auth.deps import DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse
from app.dev import runtime as dev_runtime
from app.schemas.dev_runtime import (
    DevRequeueResp,
    QueuePurgeResp,
    QueueStatsResp,
    RedisFlushReq,
    RedisFlushResp,
    RuntimeStatusResp,
)

router = APIRouter(prefix="/dev", tags=["dev"])


def _require_dev() -> None:
    if settings.env != "development":
        raise AppError(ErrorCode.FORBIDDEN, "dev endpoint disabled")


def _require_flush_confirm(confirm: str) -> None:
    if confirm != "FLUSH":
        raise AppError(ErrorCode.VALIDATION_ERROR, 'confirm must be "FLUSH"')


@router.get("/verification-code")
async def peek_verification_code(
    r: RedisClient,
    email: str = Query(..., min_length=3),
) -> ApiResponse[dict[str, str]]:
    _require_dev()
    key = f"dev:verify:{email.strip().lower()}"
    code = await r.get(key)
    if not code:
        raise AppError(ErrorCode.VALIDATION_ERROR, "no pending verification code for this email")
    return ApiResponse(data={"code": str(code)})


@router.get("/runtime/status")
async def runtime_status(r: RedisClient) -> ApiResponse[RuntimeStatusResp]:
    """Redis key counts by scope + RabbitMQ queue depth."""
    _require_dev()
    data = await dev_runtime.get_runtime_status(r)
    return ApiResponse(data=RuntimeStatusResp.model_validate(data))


@router.get("/queue/stats")
async def queue_stats() -> ApiResponse[QueueStatsResp]:
    _require_dev()
    data = await dev_runtime.get_queue_stats()
    return ApiResponse(data=QueueStatsResp.model_validate(data))


@router.post("/queue/purge")
async def queue_purge(confirm: str = Query(...)) -> ApiResponse[QueuePurgeResp]:
    """Purge pending worker tasks (e.g. after worker crash during debug)."""
    _require_dev()
    _require_flush_confirm(confirm)
    data = await dev_runtime.purge_queue()
    return ApiResponse(data=QueuePurgeResp.model_validate(data))


@router.post("/redis/flush")
async def redis_flush(body: RedisFlushReq, r: RedisClient) -> ApiResponse[RedisFlushResp]:
    """Delete Redis keys by scope. Use run_id with forge scope for a single run."""
    _require_dev()
    _require_flush_confirm(body.confirm)
    deleted = await dev_runtime.flush_redis(
        r, body.scopes, run_id=body.run_id, pattern=body.pattern
    )
    return ApiResponse(data=RedisFlushResp(deleted=deleted))


@router.post("/runs/{run_id}/requeue")
async def requeue_run(
    run_id: UUID,
    r: RedisClient,
    db: DbSession,
) -> ApiResponse[DevRequeueResp]:
    """Re-enqueue a stuck run after worker restart."""
    _require_dev()
    data = await dev_runtime.dev_requeue_run(db, r, run_id)
    return ApiResponse(data=DevRequeueResp.model_validate(data))
