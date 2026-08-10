"""任务分发：consumer 收到消息后路由到 email / forge handler。"""

from __future__ import annotations

import uuid

import redis.asyncio as redis

from app.core.config import settings
from app.email.worker import (
    send_notification_email,
    send_reset_email,
    send_verification_email,
)
from app.forge.event_log import bind_event_redis
from app.forge.runner import execute_run, resume_run
from app.messaging.tasks import (
    TASK_EXECUTE_RUN,
    TASK_RESUME_RUN,
    TASK_SCAN_SCHEDULES,
    TASK_SEND_NOTIFICATION,
    TASK_SEND_RESET,
    TASK_SEND_VERIFICATION,
)

# 全局 Redis 客户端实例，用于缓存连接
_redis: redis.Redis | None = None


def _worker_redis() -> redis.Redis:
    """
    获取或创建 Worker 专用的 Redis 客户端。
    
    采用单例模式：首次调用时创建连接，后续复用。
    
    返回：
        redis.Redis: 异步 Redis 客户端实例
    """
    global _redis
    if _redis is None:
        # 从配置中读取 Redis URL 并创建连接
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def worker_ctx() -> dict:
    """
    构造 Worker 上下文对象。
    
    将 Worker 需要的公共资源（如 Redis 连接）打包成字典，
    传递给各个处理函数，避免全局变量污染。
    
    返回：
        dict: 包含 Redis 客户端等资源的上下文字典
    """
    return {"redis": _worker_redis()}


async def dispatch_task(task: str, payload: dict) -> None:
    """
    任务分发器：根据任务类型路由到对应的处理函数。
    
    这是 Worker 消息处理的核心路由函数。收到消息后，
    根据 task 字段的值，调用不同的处理函数。
    
    参数：
        task: 任务类型字符串（如 'execute_run'）
        payload: 任务参数载荷（字典格式）
    
    异常：
        ValueError: 当 task 类型未知时抛出
    """
    # 1. 获取 Worker 上下文（包含 Redis 连接）
    ctx = worker_ctx()
    # 2. 将 Redis 连接绑定到事件日志模块（用于记录 Forge 执行事件）
    bind_event_redis(ctx["redis"])
    
    # 3. 使用 match-case 模式匹配（Python 3.10+ 的语法）
    #    根据不同的任务类型，调用对应的处理函数
    match task:
        # 发送注册验证码邮件
        case _ if task == TASK_SEND_VERIFICATION:
            await send_verification_email(ctx, payload["email"], payload["code"])
        
        # 发送密码重置邮件
        case _ if task == TASK_SEND_RESET:
            await send_reset_email(ctx, payload["email"], payload["token"])
        
        # 发送通用通知邮件
        case _ if task == TASK_SEND_NOTIFICATION:
            await send_notification_email(
                ctx, payload["email"], payload["subject"], payload["body"]
            )
        
        # 执行游戏生成任务（首次执行）
        case _ if task == TASK_EXECUTE_RUN:
            # 将 run_id 字符串转换为 UUID 对象
            await execute_run(ctx, uuid.UUID(payload["run_id"]))
        
        # 恢复已暂停的游戏生成任务（用户确认策划稿后继续）
        case _ if task == TASK_RESUME_RUN:
            await resume_run(
                ctx,
                uuid.UUID(payload["run_id"]),
                payload["decision"],          # 用户决策：approve / modify / reject
                payload.get("modify_text"),   # 如果是修改，用户输入的修改意见
            )
        
        # 扫描定时任务（如游戏定时下架）
        case _ if task == TASK_SCAN_SCHEDULES:
            from app.core import db as dbmod
            from app.scheduler.services import scan_scheduled

            # 创建数据库会话，执行定时扫描
            async with dbmod.SessionLocal() as s:
                await scan_scheduled(s)
        
        # 未知任务类型：抛出异常（Worker 会 nack 并重新入队）
        case _:
            raise ValueError(f"unknown task: {task}")