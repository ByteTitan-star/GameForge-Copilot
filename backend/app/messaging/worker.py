"""
RabbitMQ worker 入口：`uv run python -m app.messaging.worker`
作用：启动消息队列消费者，监听并处理异步任务（邮件发送、游戏生成等）
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.messaging.handlers import dispatch_task  # 任务分发器
from app.messaging.rabbit import _task_channel, close_connection  # RabbitMQ 连接管理
from app.messaging.tasks import TASK_QUEUE, decode_task  # 队列名称和消息解码

log = logging.getLogger(__name__)


def _is_transport_reset_noise(context: dict[str, object]) -> bool:
    """
    判断是否为 Windows 上传输层重置的噪音错误。
    
    背景：Windows + asyncio 环境下，当远程服务器（如 SMTP 邮件服务器）主动关闭连接时，
    asyncio 会抛出 ConnectionResetError (WinError 10054)。
    这通常发生在邮件已成功发送后的连接清理阶段，不影响业务功能。
    
    参数：
        context: asyncio 异常上下文，包含 'exception' 和 'message' 字段
    
    返回：
        bool: 如果是已知噪音错误返回 True，否则返回 False
    """
    return isinstance(
        context.get("exception"), ConnectionResetError
    ) and "_call_connection_lost" in str(context.get("message", ""))


def _worker_loop_exception_handler(
    loop: asyncio.AbstractEventLoop, context: dict[str, object]
) -> None:
    """
    自定义 asyncio 事件循环异常处理器。
    
    作用：
        1. 捕获并降级 Windows 上连接清理的噪音错误（避免污染日志）
        2. 其他异常走默认处理流程
    
    参数：
        loop: asyncio 事件循环
        context: 异常上下文信息
    """
    # 如果是已知的传输层重置噪音，只记录 debug 级别日志，不报错
    if _is_transport_reset_noise(context):
        log.debug(
            "transport shutdown after peer close (ignored): %s",
            context.get("message"),
        )
        return
    # 其他异常交给默认处理器
    loop.default_exception_handler(context)


async def _scheduler_loop() -> None:
    """
    定时任务调度循环（后台协程）。
    
    功能：每分钟执行一次定时扫描
    用途：
        - 检查并处理到期的游戏下架任务（B8 功能）
        - 类似 cron 的定时任务
    
    注意：这是一个独立的协程，和消息消费并行运行
    """
    from app.core import db as dbmod
    from app.scheduler.services import scan_scheduled

    while True:
        await asyncio.sleep(60)  # 每分钟执行一次
        try:
            async with dbmod.SessionLocal() as s:
                n = await scan_scheduled(s)  # 执行定时下架扫描
                if n:
                    log.info("scheduled take_down count=%s", n)
        except Exception:
            log.exception("scheduler scan failed")  # 出错时记录日志，不影响主循环


async def _consume() -> None:
    """
    消息消费主协程（Worker 的核心逻辑）。
    
    执行流程：
        1. 设置自定义异常处理器
        2. 启动定时任务调度协程（后台运行）
        3. 连接 RabbitMQ，声明队列
        4. 进入消息消费循环，持续监听队列
        5. 收到消息 → 解码 → 分发到对应的处理器执行
        6. 执行完成后确认消息，继续等待下一条
    
    注意：
        - message.process(requeue=True)：处理失败时重新入队
        - queue.iterator()：异步迭代器，持续监听新消息
    """
    # 1. 设置事件循环的自定义异常处理器
    asyncio.get_running_loop().set_exception_handler(_worker_loop_exception_handler)
    
    # 2. 启动定时任务扫描协程（并发执行）
    scan_task = asyncio.create_task(_scheduler_loop())
    
    try:
        # 3. 连接 RabbitMQ，获取 channel 和交换器
        channel, _exchange = await _task_channel()
        
        # 4. 声明队列（如果不存在则创建，持久化）
        queue = await channel.declare_queue(TASK_QUEUE, durable=True)
        log.info("worker listening on queue=%s url=%s", TASK_QUEUE, settings.rabbitmq_url)

        # 5. 进入消息消费循环
        async with queue.iterator() as it:
            async for message in it:  # 持续等待新消息
                # 处理消息，requeue=True 表示失败时重新入队
                async with message.process(requeue=True):
                    # 6. 解码消息体：提取任务名和载荷数据
                    task, payload = decode_task(message.body)
                    log.info("task=%s payload_keys=%s", task, list(payload.keys()))
                    
                    # 7. 分发并执行任务
                    try:
                        await dispatch_task(task, payload)
                    except Exception:
                        # 任务执行失败，记录错误日志并重新抛出（触发重新入队）
                        log.exception("task=%s failed", task)
                        raise
    finally:
        # 8. 清理资源：取消定时任务，flush langfuse，关闭 RabbitMQ 连接
        scan_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scan_task
        from app.core.langfuse import flush_langfuse

        flush_langfuse()
        await close_connection()


def main() -> None:
    """
    Worker 主入口函数。
    
    执行步骤：
        1. 配置日志系统（指定服务名为 'worker'）
        2. 启动异步消息消费协程
        3. 处理键盘中断（Ctrl+C）优雅退出
    """
    # 初始化日志：服务标识为 "worker"，按配置的级别和目录输出
    setup_logging(settings.log_level, service="worker", log_dir=settings.log_dir)
    # worker 是独立进程，需各自注册 langfuse 单例（run_generation 在此进程跑）
    from app.core.langfuse import init_langfuse

    init_langfuse()
    
    # 运行异步主协程，捕获 Ctrl+C 信号
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_consume())


# 脚本入口：当直接执行 python -m app.messaging.worker 时运行
if __name__ == "__main__":
    main()