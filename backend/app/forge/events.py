"""WS 事件发布：组 WSEvent → RabbitMQ topic `run.{run_id}`（或 memory 总线）。

WS 端点订阅同 routing key 转发；跨进程（worker 发布，uvicorn 转发）。docs/10 §5。
每个事件同时写入 Redis 环形缓冲，供刷新后 replay。
"""

import uuid
from datetime import UTC, datetime

from app.enums import WSEventType
from app.forge.event_log import _client, append_event, next_event_seq
from app.messaging.factory import get_ws_bus
from app.schemas.ws import WSEvent


async def publish_event(
    run_id: uuid.UUID,
    event_type: WSEventType,
    payload: dict,
) -> None:
    """组装 WSEvent 并发布到 RabbitMQ topic，同时写入 Redis 环形缓冲。

    场景：graph 节点进度/阶段/HITL 状态推送到前端 WebSocket。
    参数：run_id - 生成任务 ID；event_type - WS 事件类型；payload - 事件载荷 dict。
    返回：无。
    """
    client, owned = await _client()
    try:
        seq = await next_event_seq(client, run_id)
        ev = WSEvent(
            type=event_type,
            run_id=run_id,
            ts=datetime.now(UTC),
            seq=seq,
            payload=payload,
        )
        data = ev.model_dump_json()
        await append_event(client, run_id, data)
        await get_ws_bus().publish_data(run_id, data)
    finally:
        if owned:
            await client.aclose()
