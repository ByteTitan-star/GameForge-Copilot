"""WS 事件发布：组 WSEvent → RabbitMQ topic `run.{run_id}`（或 memory 总线）。

WS 端点订阅同 routing key 转发；跨进程（worker 发布，uvicorn 转发）。docs/10 §5。
"""

import uuid

from app.enums import WSEventType
from app.messaging.factory import get_ws_bus


async def publish_event(
    run_id: uuid.UUID,
    event_type: WSEventType,
    payload: dict,
) -> None:
    await get_ws_bus().publish(run_id, event_type, payload)
