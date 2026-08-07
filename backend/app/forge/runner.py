"""生成执行器 worker 入口：execute_run（首次，到 HITL 中断）、resume_run（HITL 后续跑）。

真实生成在 app.forge.graph.run_generation；本文件仅任务 handler 包装。
"""

import uuid

from app.forge.graph import run_generation


async def execute_run(ctx: dict, run_id: uuid.UUID) -> None:
    """首次执行：plan → HITL 中断（不发 done）。"""
    from app.forge.event_log import bind_event_redis

    bind_event_redis(ctx.get("redis"))
    await run_generation(ctx, run_id, resume=False)


async def resume_run(
    ctx: dict, run_id: uuid.UUID, decision: str, modify_text: str | None = None
) -> None:
    """HITL 解决后续行：art→code→qa→done。"""
    from app.forge.event_log import bind_event_redis

    bind_event_redis(ctx.get("redis"))
    await run_generation(ctx, run_id, resume=True, decision=decision, modify_text=modify_text)


__all__ = ["execute_run", "resume_run"]
