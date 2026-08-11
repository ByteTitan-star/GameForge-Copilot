"""生成执行器 worker 入口：execute_run（首次，到 HITL 中断）、resume_run（HITL 后续跑）。

真实生成在 app.forge.graph.run_generation；本文件仅任务 handler 包装。

幂等：broker 是 at-least-once（worker 崩溃/断连会重投同一条消息），同一 run
并发执行会导致重复 LLM 调用、重复版本号、重复计费。入口用 ``run:executing:{run_id}``
短锁吸收重投：已持锁则跳过本次，正常结束在 finally 释放；崩溃则由 TTL 兜底。
"""

import logging
import uuid

from app.forge.graph import run_generation

log = logging.getLogger(__name__)

# 锁 TTL：需大于单次 run 最长耗时（含多轮 LLM/沙箱）。正常路径在 finally 主动释放，
# 仅在 worker 崩溃时由 TTL 兜底——届时重投会阻塞到过期，避免与未结束的旧执行并发。
EXEC_LOCK_TTL = 7_200


async def _acquire_exec_lock(redis, run_id: uuid.UUID) -> bool:
    """获取执行锁；redis 缺省（不应发生）时放行，不阻塞主流程。"""
    if redis is None:
        return True
    return bool(await redis.set(f"run:executing:{run_id}", "1", nx=True, ex=EXEC_LOCK_TTL))


async def _release_exec_lock(redis, run_id: uuid.UUID) -> None:
    if redis is None:
        return
    await redis.delete(f"run:executing:{run_id}")


async def execute_run(ctx: dict, run_id: uuid.UUID) -> None:
    """首次执行：plan → HITL 中断（不发 done）。"""
    from app.forge.event_log import bind_event_redis

    if not await _acquire_exec_lock(ctx.get("redis"), run_id):
        log.info("skip redelivered execute_run, already executing run_id=%s", run_id)
        return
    try:
        bind_event_redis(ctx.get("redis"))
        await run_generation(ctx, run_id, resume=False)
    finally:
        await _release_exec_lock(ctx.get("redis"), run_id)


async def resume_run(
    ctx: dict, run_id: uuid.UUID, decision: str, modify_text: str | None = None
) -> None:
    """HITL 解决后续行：art→code→qa→done。"""
    from app.forge.event_log import bind_event_redis

    if not await _acquire_exec_lock(ctx.get("redis"), run_id):
        log.info("skip redelivered resume_run, already executing run_id=%s", run_id)
        return
    try:
        bind_event_redis(ctx.get("redis"))
        await run_generation(
            ctx, run_id, resume=True, decision=decision, modify_text=modify_text
        )
    finally:
        await _release_exec_lock(ctx.get("redis"), run_id)


__all__ = ["execute_run", "resume_run"]
