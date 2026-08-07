"""按配置选择 RabbitMQ 或 memory 后端。"""

from __future__ import annotations

from app.core.config import settings
from app.messaging.memory import MemoryTaskPublisher, MemoryWsBus
from app.messaging.rabbit import RabbitTaskPublisher, RabbitWsBus

_task_publisher: MemoryTaskPublisher | RabbitTaskPublisher | None = None
_ws_bus: MemoryWsBus | RabbitWsBus | None = None


def use_memory() -> bool:
    return settings.messaging_backend == "memory"


def get_task_publisher() -> MemoryTaskPublisher | RabbitTaskPublisher:
    global _task_publisher
    if _task_publisher is None:
        _task_publisher = MemoryTaskPublisher() if use_memory() else RabbitTaskPublisher()
    return _task_publisher


def get_ws_bus() -> MemoryWsBus | RabbitWsBus:
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
