"""生成执行器 worker 入口：execute_run（首次，到 HITL 中断）、resume_run（HITL 后续跑）。

真实生成在 app.forge.graph.run_generation；本文件仅任务 handler 包装。

幂等：broker 是 at-least-once（worker 崩溃/断连会重投同一条消息），同一 run
并发执行会导致重复 LLM 调用、重复版本号、重复计费。入口用 ``run:executing:{run_id}``
短租约串行化执行：冲突时抛错让 broker 重投，正常结束在 finally 释放；崩溃由 TTL 兜底。
"""

import asyncio
import contextlib
import logging
import uuid

from app.forge.commands import command_already_succeeded, mark_command_succeeded
from app.forge.graph import run_generation

log = logging.getLogger(__name__)

# 短 TTL 配合心跳续租，worker 崩溃后任务最多等待一个租约周期即可重投。
EXEC_LOCK_TTL = 90
EXEC_LOCK_HEARTBEAT = 30


class TaskLeaseBusy(RuntimeError):
    """Another worker owns the execution lease; the broker must retry the task."""


class TaskLeaseLost(RuntimeError):
    """The worker lost its execution lease and must stop to avoid duplicate work."""


async def _acquire_exec_lock(redis, run_id: uuid.UUID) -> str | None:
    """获取 run 执行的短租约（owner token）。

    场景：``_run_with_lease`` 防止 at-least-once broker 重复执行同一 run。
    参数：redis - Redis 客户端；run_id - 生成任务 ID。
    返回：成功时返回 owner token；无 Redis 时返回 None；冲突时抛 TaskLeaseBusy。
    """
    if redis is None:
        return None
    owner = uuid.uuid4().hex
    acquired = await redis.set(f"run:executing:{run_id}", owner, nx=True, ex=EXEC_LOCK_TTL)
    if not acquired:
        raise TaskLeaseBusy(f"run {run_id} is already executing")
    return owner


async def _compare_expire(redis, key: str, owner: str, ttl: int) -> bool:
    """CAS 续租：仅当 key 仍属于 owner 时刷新 TTL。

    场景：``_lease_heartbeat`` 周期性续租执行锁。
    参数：redis - Redis 客户端；key - 锁键；owner - 持有者 token；ttl - 新 TTL 秒数。
    返回：续租成功为 True，锁已丢失或不属于 owner 为 False。
    """
    from redis.exceptions import WatchError

    for _ in range(3):
        async with redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key)
                if await pipe.get(key) != owner:
                    return False
                pipe.multi()
                pipe.expire(key, ttl)
                result = await pipe.execute()
                return bool(result[0])
            except WatchError:
                continue
    return False


async def _release_exec_lock(redis, run_id: uuid.UUID, owner: str | None) -> None:
    """CAS 释放 run 执行锁（仅 owner 可删）。

    场景：``_run_with_lease`` finally 块正常结束或异常退出时释放。
    参数：redis - Redis 客户端；run_id - 生成任务 ID；owner - 持有者 token。
    返回：无。
    """
    if redis is None or owner is None:
        return
    from redis.exceptions import WatchError

    key = f"run:executing:{run_id}"
    for _ in range(3):
        async with redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key)
                if await pipe.get(key) != owner:
                    return
                pipe.multi()
                pipe.delete(key)
                await pipe.execute()
                return
            except WatchError:
                continue


async def _lease_heartbeat(redis, run_id: uuid.UUID, owner: str) -> None:
    """周期性续租执行锁，丢失时抛 TaskLeaseLost。

    场景：``_run_with_lease`` 后台协程，防止 worker 崩溃后锁永久占用。
    参数：redis - Redis 客户端；run_id - 生成任务 ID；owner - 持有者 token。
    返回：无；租约丢失时抛 TaskLeaseLost 以取消主任务。
    """
    key = f"run:executing:{run_id}"
    while True:
        await asyncio.sleep(EXEC_LOCK_HEARTBEAT)
        if not await _compare_expire(redis, key, owner, EXEC_LOCK_TTL):
            raise TaskLeaseLost(f"execution lease lost for run {run_id}")


async def _run_with_lease(redis, run_id: uuid.UUID, operation) -> None:
    """在租约保护下执行 operation，确保同一 run 串行执行。

    场景：``execute_run`` / ``resume_run`` 入口包装。
    参数：redis - Redis 客户端；run_id - 生成任务 ID；operation - 无参异步可调用对象。
    返回：无；租约冲突或丢失时抛对应异常。
    """
    owner = await _acquire_exec_lock(redis, run_id)
    heartbeat: asyncio.Task | None = None
    work: asyncio.Task | None = None
    try:
        if owner is None:
            await operation()
            return
        heartbeat = asyncio.create_task(_lease_heartbeat(redis, run_id, owner))
        work = asyncio.create_task(operation())
        done, _ = await asyncio.wait({heartbeat, work}, return_when=asyncio.FIRST_COMPLETED)
        if heartbeat in done:
            work.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await work
            await heartbeat
        await work
    finally:
        if heartbeat is not None:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
        await _release_exec_lock(redis, run_id, owner)


async def execute_run(ctx: dict, run_id: uuid.UUID) -> None:
    """首次执行生成任务：plan → HITL 中断（不发 done）。

    场景：RabbitMQ worker 消费 TASK_EXECUTE_RUN。
    参数：ctx - 含 redis 等的 worker 上下文；run_id - 生成任务 ID。
    返回：无。
    """
    from app.forge.event_log import bind_event_redis

    async def operation() -> None:
        """在租约保护下执行首次 run_generation。

        场景：execute_run worker 回调。
        参数：无（闭包捕获 ctx、run_id）。
        返回：无。
        """
        bind_event_redis(ctx.get("redis"))
        await run_generation(ctx, run_id, resume=False)

    await _run_with_lease(ctx.get("redis"), run_id, operation)


async def resume_run(
    ctx: dict,
    run_id: uuid.UUID,
    decision: str,
    modify_text: str | None = None,
    command_id: uuid.UUID | None = None,
) -> None:
    """HITL 解决后续行：art→code→qa→done。

    场景：RabbitMQ worker 消费 TASK_RESUME_RUN；支持 command 幂等跳过。
    参数：
        ctx - 含 redis 等的 worker 上下文；
        run_id - 生成任务 ID；
        decision - 用户决策（approve/modify/select_a 等）；
        modify_text - 可选修改意见；
        command_id - 可选 RunCommand ID（幂等检查）。
    返回：无；command 已成功则直接返回。
    """
    from app.forge.event_log import bind_event_redis

    if command_id is not None and await command_already_succeeded(command_id):
        return

    async def operation() -> None:
        """绑定 Redis、执行 resume 生成并标记命令成功。

        场景：``resume_run`` 在租约保护下的实际工作协程。
        参数：无（闭包捕获 ctx、run_id、decision、modify_text、command_id）。
        返回：无。
        """
        bind_event_redis(ctx.get("redis"))
        if command_id is not None:
            await mark_command_succeeded(command_id)

    await _run_with_lease(ctx.get("redis"), run_id, operation)


__all__ = ["TaskLeaseBusy", "TaskLeaseLost", "execute_run", "resume_run"]
