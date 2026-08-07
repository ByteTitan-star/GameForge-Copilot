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
    """存活检查（进程在），无需鉴权。"""
    return ApiResponse(data=Health())


@router.get("/ready", response_model=ApiResponse[Ready])
async def ready(db: DbSession, r: RedisClient) -> ApiResponse[Ready]:
    """就绪检查：DB + Redis + RabbitMQ（memory 后端时 rabbitmq=true）。"""
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
