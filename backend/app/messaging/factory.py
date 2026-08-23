"""按配置选择 RabbitMQ 或 memory 后端。测试使用"""

from __future__ import annotations

from app.core.config import settings
from app.messaging.memory import MemoryTaskPublisher, MemoryWsBus
from app.messaging.rabbit import RabbitTaskPublisher, RabbitWsBus

_task_publisher: MemoryTaskPublisher | RabbitTaskPublisher | None = None
_ws_bus: MemoryWsBus | RabbitWsBus | None = None


def use_memory() -> bool:
    """判断是否使用进程内 memory 消息后端。

    场景：factory 选择 RabbitMQ 或 memory。
    返回：messaging_backend == memory 时为 True。
    """
    return settings.messaging_backend == "memory"


def get_task_publisher() -> MemoryTaskPublisher | RabbitTaskPublisher:
    """返回单例任务发布器（RabbitMQ 或 memory）。

    场景：outbox dispatch、API 提交 Forge 任务。
    返回：MemoryTaskPublisher 或 RabbitTaskPublisher。
    """
    global _task_publisher
    if _task_publisher is None:
        _task_publisher = MemoryTaskPublisher() if use_memory() else RabbitTaskPublisher()
    return _task_publisher


def get_ws_bus() -> MemoryWsBus | RabbitWsBus:
    """返回单例 WebSocket 事件总线。

    场景：Forge 推送进度、WS runs 订阅。
    返回：MemoryWsBus 或 RabbitWsBus。
    """
    global _ws_bus
    if _ws_bus is None:
        _ws_bus = MemoryWsBus() if use_memory() else RabbitWsBus()
    return _ws_bus


def reset_messaging() -> None:
    """测试 teardown：重置单例与 memory 捕获。"""
    global _task_publisher, _ws_bus
    MemoryTaskPublisher.reset()
    MemoryWsBus.reset()
    _task_publisher = None
    _ws_bus = None
