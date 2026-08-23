"""run 控制面：用户暂停/取消通过 Redis 标志；节点间检查。"""

import uuid

import redis.asyncio as redis

_KEY = "run:ctrl:{run_id}"


async def request_pause(r: redis.Redis, run_id: uuid.UUID) -> None:
    """设置 run 暂停标志，节点间 poll 后中断执行。

    场景：用户点击暂停按钮。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：无；标志 TTL 24 小时。
    """
    await r.set(_KEY.format(run_id=run_id), "pause", ex=86400)


async def request_cancel(r: redis.Redis, run_id: uuid.UUID) -> None:
    """设置 run 取消标志，节点间 poll 后终止执行。

    场景：用户点击取消按钮。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：无；标志 TTL 24 小时。
    """
    await r.set(_KEY.format(run_id=run_id), "cancel", ex=86400)


async def clear_control(r: redis.Redis, run_id: uuid.UUID) -> None:
    """清除 run 的暂停/取消控制标志。

    场景：run 正常结束或 resume 后重置控制面。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：无。
    """
    await r.delete(_KEY.format(run_id=run_id))


async def poll_control(r: redis.Redis, run_id: uuid.UUID) -> str | None:
    """轮询 run 控制标志。

    场景：graph 节点间检查用户是否请求暂停或取消。
    参数：r - Redis 客户端；run_id - 生成任务 ID。
    返回：'pause' | 'cancel' | None。
    """
    v = await r.get(_KEY.format(run_id=run_id))
    return v if v in ("pause", "cancel") else None
