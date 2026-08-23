from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.auth.deps import DbSession, RedisClient
from app.core.response import ApiResponse
from app.messaging.factory import use_memory
from app.messaging.rabbit import ping_rabbitmq

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str = "ok"


class Ready(BaseModel):
    db: bool
    redis: bool
    rabbitmq: bool


@router.get("/healthz", response_model=ApiResponse[Health])
async def health() -> ApiResponse[Health]:
    """进程存活探针。

    作用：确认 API 进程可响应请求。
    场景：K8s liveness / 负载均衡健康检查，无需鉴权。
    参数：无。
    返回：ApiResponse，data.status 为 "ok"。
    """
    return ApiResponse(data=Health())


@router.get("/ready", response_model=ApiResponse[Ready])
async def ready(db: DbSession, r: RedisClient) -> ApiResponse[Ready]:
    """依赖就绪探针。

    作用：探测 DB、Redis、RabbitMQ（memory 后端时 rabbitmq 恒为 true）是否可用。
    场景：K8s readiness / 部署后冒烟，无需鉴权。
    参数：db — 数据库会话；r — Redis 客户端。
    返回：ApiResponse，data 含 db/redis/rabbitmq 布尔就绪态。
    """
    db_ok = True
    try:
        await db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 探针
        db_ok = False
    redis_ok = True
    try:
        await r.ping()
    except Exception:  # noqa: BLE001
        redis_ok = False
    mq_ok = True if use_memory() else await ping_rabbitmq()
    return ApiResponse(data=Ready(db=db_ok, redis=redis_ok, rabbitmq=mq_ok))
