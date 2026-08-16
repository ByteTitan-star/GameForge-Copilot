"""
RabbitMQ worker 入口：`uv run python -m app.messaging.worker`
作用：启动消息队列消费者，监听并处理异步任务（邮件发送、游戏生成等）
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any, cast

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.security_boot import assert_production_secrets
from app.messaging.handlers import dispatch_task  # 任务分发器
from app.messaging.rabbit import _task_channel, close_connection  # RabbitMQ 连接管理
from app.messaging.tasks import (  # 队列名称和消息解码
    HEADER_RETRY_COUNT,
    TASK_DLQ,
    TASK_QUEUE,
    decode_task,
)

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from aio_pika.abc import AbstractIncomingMessage


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
        - 回收超时仍 PAUSED 的 HIL/暂停 run，释放并发额度
    """
    from app.core import db as dbmod
    from app.messaging.handlers import _worker_redis
    from app.scheduler.services import expire_stale_paused_runs, scan_scheduled

    while True:
        await asyncio.sleep(60)  # 每分钟执行一次
        try:
            async with dbmod.SessionLocal() as s:
                n = await scan_scheduled(s)  # 执行定时下架扫描
                if n:
                    log.info("scheduled take_down count=%s", n)
        except Exception:
            log.exception("scheduler scan failed")  # 出错时记录日志，不影响主循环
        try:
            async with dbmod.SessionLocal() as s:
                n = await expire_stale_paused_runs(s, _worker_redis())
                if n:
                    log.info("hil wait timeout expired count=%s", n)
        except Exception:
            log.exception("hil wait timeout scan failed")


async def _outbox_loop() -> None:
    from app.messaging.outbox import dispatch_pending

    while True:
        try:
            await dispatch_pending()
        except Exception:
            log.exception("outbox dispatch failed")
        await asyncio.sleep(2)


def _message_retry_count(message: AbstractIncomingMessage) -> int:
    """读取应用层重投计数；非法/缺失按 0 处理。"""
    headers = message.headers or {}
    raw = headers.get(HEADER_RETRY_COUNT, 0)
    try:
        return max(0, int(cast(Any, raw)))
    except (TypeError, ValueError):
        return 0


def _merged_headers(message: AbstractIncomingMessage, **extra: Any) -> dict[str, Any]:
    headers: dict[str, Any] = dict(message.headers or {})
    headers.update(extra)
    return headers


async def _republish_task(message: AbstractIncomingMessage, task: str, *, retry_count: int) -> None:
    """带递增重试计数重新入队（ack 原消息后由调用方完成）。"""
    import aio_pika
    from aio_pika import Message

    try:
        channel, exchange = await _task_channel()
        try:
            await exchange.publish(
                Message(
                    body=message.body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    headers=_merged_headers(message, **{HEADER_RETRY_COUNT: retry_count}),
                ),
                routing_key=task,
            )
        finally:
            await channel.close()
    except Exception:
        log.exception("republish failed task=%s retry=%s", task, retry_count)


async def _publish_to_dlq(
    message: AbstractIncomingMessage, task: str, *, retry_count: int, error: str
) -> None:
    """毒消息写入死信队列，保留原 body 与失败元数据。"""
    import aio_pika
    from aio_pika import Message

    try:
        channel, _exchange = await _task_channel()
        try:
            await channel.declare_queue(TASK_DLQ, durable=True)
            await channel.default_exchange.publish(
                Message(
                    body=message.body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    headers=_merged_headers(
                        message,
                        **{
                            HEADER_RETRY_COUNT: retry_count,
                            "x-death-task": task,
                            "x-death-reason": error[:500],
                        },
                    ),
                ),
                routing_key=TASK_DLQ,
            )
        finally:
            await channel.close()
    except Exception:
        log.exception("DLQ publish failed task=%s retry=%s", task, retry_count)


def _retry_backoff_seconds(retry: int) -> float:
    """指数退避，上限 60s（ADR-08 租约 busy / 失败重投）。"""
    return float(min(60, 2 ** max(0, retry)))


async def _run_one(message: AbstractIncomingMessage) -> None:
    """处理单条消息。

    成功 → ack；TaskLeaseBusy → 递增计数 + 指数退避重投；
    其他失败 → 递增 x-retry-count 退避重投，超过 worker_max_redeliveries 写入 DLQ 后 ack。
    避免毒消息无限占用 prefetch 槽位。
    """
    # requeue=False：由本函数显式 republish / DLQ，避免无计数的裸 nack 循环
    async with message.process(requeue=False):
        retry = _message_retry_count(message)
        try:
            task, payload = decode_task(message.body)
        except Exception as exc:
            log.exception("decode_task failed; routing to DLQ")
            await _publish_to_dlq(message, "undecodable", retry_count=retry, error=str(exc))
            return

        log.info(
            "task=%s payload_keys=%s retry=%s",
            task,
            list(payload.keys()),
            retry,
        )
        try:
            await dispatch_task(task, payload)
        except Exception as exc:
            from app.forge.runner import TaskLeaseBusy

            max_retries = settings.worker_max_redeliveries
            if isinstance(exc, TaskLeaseBusy):
                if retry >= max_retries:
                    log.warning(
                        "task lease busy → DLQ after %s retries task=%s",
                        retry,
                        task,
                    )
                    await _publish_to_dlq(message, task, retry_count=retry, error=str(exc))
                    return
                next_retry = retry + 1
                delay = _retry_backoff_seconds(retry)
                await asyncio.sleep(delay)
                log.info(
                    "task lease busy; requeue task=%s retry=%s/%s delay=%.0fs",
                    task,
                    next_retry,
                    max_retries,
                    delay,
                )
                await _republish_task(message, task, retry_count=next_retry)
                return

            if retry >= max_retries:
                log.exception(
                    "task=%s poison → DLQ after %s retries",
                    task,
                    retry,
                )
                await _publish_to_dlq(message, task, retry_count=retry, error=str(exc))
                return

            next_retry = retry + 1
            delay = _retry_backoff_seconds(retry)
            log.exception(
                "task=%s failed; requeue retry=%s/%s delay=%.0fs",
                task,
                next_retry,
                max_retries,
                delay,
            )
            await asyncio.sleep(delay)
            await _republish_task(message, task, retry_count=next_retry)


async def _consume_once(in_flight: set[asyncio.Task]) -> None:
    """单次连接消费循环；连接断开或异常由外层重连。"""
    channel, _exchange = await _task_channel()
    try:
        await channel.set_qos(prefetch_count=settings.max_concurrent_tasks)
        queue = await channel.declare_queue(TASK_QUEUE, durable=True)
        log.info(
            "worker listening queue=%s concurrency=%s url=%s",
            TASK_QUEUE,
            settings.max_concurrent_tasks,
            settings.rabbitmq_url,
        )
        async with queue.iterator() as it:
            async for message in it:
                handler = asyncio.create_task(_run_one(message))
                in_flight.add(handler)
                handler.add_done_callback(in_flight.discard)
    finally:
        with contextlib.suppress(Exception):
            await channel.close()


async def _consume() -> None:
    """
    消息消费主协程：prefetch 有界并发，每条消息独立 task 执行。

    并发模型（docs/02 §可观测）：
        - channel.set_qos(prefetch_count=N)：broker 最多投 N 条未 ack 消息 → 并发=N 且自带背压。
        - 每条消息起一个 _run_one task：ack 在该 task 结束时触发，长 LLM 不阻塞消费循环。
        - asyncio.create_task 拷贝 contextvars，各 run 的 trace_id/run_id/user_id 互不串扰。
        - 水平扩容：多开 worker 进程（docker compose --scale worker=N），竞争消费同一队列。
        - 外层指数退避重连：单次消费异常不拖死进程（ADR-08）。
    """
    asyncio.get_running_loop().set_exception_handler(_worker_loop_exception_handler)

    scan_task = asyncio.create_task(_scheduler_loop())
    outbox_task = asyncio.create_task(_outbox_loop())
    in_flight: set[asyncio.Task] = set()
    backoff = 1.0
    try:
        while True:
            try:
                await _consume_once(in_flight)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("worker consume failed; reconnect in %.0fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(60.0, backoff * 2)
    finally:
        scan_task.cancel()
        outbox_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scan_task
        with contextlib.suppress(asyncio.CancelledError):
            await outbox_task
        if in_flight:
            await asyncio.gather(*in_flight, return_exceptions=True)
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
    assert_production_secrets(settings)
    # worker 是独立进程，需各自注册 langfuse 单例（run_generation 在此进程跑）
    from app.core.langfuse import init_langfuse

    init_langfuse()

    # 运行异步主协程，捕获 Ctrl+C 信号
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(_consume())


# 脚本入口：当直接执行 python -m app.messaging.worker 时运行
if __name__ == "__main__":
    main()
