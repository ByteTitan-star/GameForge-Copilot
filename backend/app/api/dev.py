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
    DevResetResp,
    QueuePurgeResp,
    QueueStatsResp,
    RedisFlushReq,
    RedisFlushResp,
    RuntimeStatusResp,
)

router = APIRouter(prefix="/dev", tags=["dev"])


def _require_dev() -> None:
    """校验当前环境为 development。

    作用：非 development 环境拒绝 dev 端点。
    场景：所有 /dev 路由入口守卫。
    参数：无。
    返回：无；不满足时抛 FORBIDDEN。
    """
    if settings.env != "development":
        raise AppError(ErrorCode.FORBIDDEN, "dev endpoint disabled")


def _require_flush_confirm(confirm: str) -> None:
    """校验破坏性操作的确认口令。

    作用：confirm 必须等于 "FLUSH" 才允许执行清队列/清 Redis 等操作。
    场景：dev 端点 purge/flush/reset 前置校验。
    参数：confirm — 用户提交的确认字符串。
    返回：无；不匹配时抛 VALIDATION_ERROR。
    """
    if confirm != "FLUSH":
        raise AppError(ErrorCode.VALIDATION_ERROR, 'confirm must be "FLUSH"')


@router.get("/verification-code")
async def peek_verification_code(
    r: RedisClient,
    email: str = Query(..., min_length=3),
) -> ApiResponse[dict[str, str]]:
    """开发环境查看邮箱验证码。

    作用：从 Redis dev 键读取待验证邮箱的 6 位码。
    场景：本地开发跳过真实邮件收信。
    参数：r — Redis；email — 目标邮箱。
    返回：ApiResponse，data.code 为验证码；无 pending 则 400。
    """
    _require_dev()
    key = f"dev:verify:{email.strip().lower()}"
    code = await r.get(key)
    if not code:
        raise AppError(ErrorCode.VALIDATION_ERROR, "no pending verification code for this email")
    return ApiResponse(data={"code": str(code)})


@router.get("/runtime/status")
async def runtime_status(r: RedisClient) -> ApiResponse[RuntimeStatusResp]:
    """查询运行时 Redis 键统计与队列深度。

    作用：汇总 forge/run 等 scope 的 Redis key 数量及 MQ 队列状态。
    场景：本地调试 forge 运行态与消息堆积。
    参数：r — Redis 客户端。
    返回：ApiResponse，data 为 RuntimeStatusResp。
    """
    _require_dev()
    data = await dev_runtime.get_runtime_status(r)
    return ApiResponse(data=RuntimeStatusResp.model_validate(data))


@router.get("/queue/stats")
async def queue_stats() -> ApiResponse[QueueStatsResp]:
    """查询 worker 任务队列统计。

    作用：返回待处理/进行中任务数量等队列指标。
    场景：开发环境排查 worker 是否消费任务。
    参数：无。
    返回：ApiResponse，data 为 QueueStatsResp。
    """
    _require_dev()
    data = await dev_runtime.get_queue_stats()
    return ApiResponse(data=QueueStatsResp.model_validate(data))


@router.post("/queue/purge")
async def queue_purge(confirm: str = Query(...)) -> ApiResponse[QueuePurgeResp]:
    """清空待处理 worker 任务队列。

    作用：purge 队列中未消费的任务（如 worker 崩溃后残留）。
    场景：开发调试；需 confirm=FLUSH。
    参数：confirm — 破坏性操作确认口令。
    返回：ApiResponse，data 为 QueuePurgeResp（含清除数量）。
    """
    _require_dev()
    _require_flush_confirm(confirm)
    data = await dev_runtime.purge_queue()
    return ApiResponse(data=QueuePurgeResp.model_validate(data))


@router.post("/redis/flush")
async def redis_flush(body: RedisFlushReq, r: RedisClient) -> ApiResponse[RedisFlushResp]:
    """按 scope 删除 Redis 键。

    作用：批量删除指定 scope 的 Redis 键，forge scope 可带 run_id 精确清理。
    场景：开发环境清理 forge 缓存或单 run 状态；需 confirm=FLUSH。
    参数：body — scope/run_id/pattern/confirm；r — Redis 客户端。
    返回：ApiResponse，data.deleted 为删除键数量。
    """
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
    """将卡住的 run 重新入队执行。

    作用：worker 重启后把 stuck run 重新 enqueue 到任务队列。
    场景：开发环境 run 卡在 running 但 worker 已退出。
    参数：run_id — 目标 run；r — Redis；db — 数据库会话。
    返回：ApiResponse，data 为 DevRequeueResp。
    """
    _require_dev()
    data = await dev_runtime.dev_requeue_run(db, r, run_id)
    return ApiResponse(data=DevRequeueResp.model_validate(data))


@router.post("/reset")
async def reset_dev(
    r: RedisClient,
    db: DbSession,
    confirm: str = Query(...),
) -> ApiResponse[DevResetResp]:
    """一键重置本地 dev forge 运行态。

    作用：失败所有 active run、清空 forge Redis、清空任务队列。
    场景：开发环境快速回到干净 forge 状态；需 confirm=FLUSH。
    参数：r — Redis；db — 数据库会话；confirm — 确认口令。
    返回：ApiResponse，data 为 DevResetResp 汇总结果。
    """
    _require_dev()
    _require_flush_confirm(confirm)
    data = await dev_runtime.reset_dev_state(db, r)
    return ApiResponse(data=DevResetResp.model_validate(data))
