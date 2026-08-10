"""
RabbitMQ 连接、任务发布、WS topic 发布/订阅。

这个文件提供了：
1. RabbitMQ 连接管理（单例连接，避免重复创建）
2. 任务发布器（API 发送任务到 Worker）
3. WebSocket 事件总线（Worker/API 推送实时进度给前端）
4. 工具函数（健康检查、队列统计、清空队列）
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message
from aio_pika.abc import AbstractChannel, AbstractConnection, AbstractQueue

from app.core.config import settings
from app.enums import WSEventType
from app.messaging.tasks import (
    TASK_EXCHANGE,
    TASK_EXECUTE_RUN,
    TASK_QUEUE,
    TASK_RESUME_RUN,
    TASK_SEND_NOTIFICATION,
    TASK_SEND_RESET,
    TASK_SEND_VERIFICATION,
    WS_EXCHANGE,
    encode_task,
)
from app.schemas.ws import WSEvent

# ============================================================
# 1. RabbitMQ 连接管理（单例模式）
# ============================================================

# 全局连接对象：整个进程共享一个 RabbitMQ 连接
_connection: AbstractConnection | None = None
# 异步锁：防止多个协程同时创建连接（线程安全）
_lock = asyncio.Lock()


async def get_connection() -> AbstractConnection:
    """
    获取或创建 RabbitMQ 全局连接（单例模式）。
    
    工作原理：
        1. 如果连接不存在或已关闭，则创建新连接
        2. 使用 asyncio.Lock 防止并发创建多个连接
        3. connect_robust 会自动重连
        
    返回：
        AbstractConnection: RabbitMQ 连接对象
    """
    global _connection
    # 快速检查：如果连接存在且未关闭，直接返回
    if _connection is None or _connection.is_closed:
        # 加锁：防止多个协程同时创建连接
        async with _lock:
            # 双重检查：获取锁后再次检查，避免重复创建
            if _connection is None or _connection.is_closed:
                # 连接到 RabbitMQ（支持自动重连）
                _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    return _connection


async def close_connection() -> None:
    """
    关闭 RabbitMQ 全局连接。
    
    使用场景：
        - Worker 优雅退出时
        - 应用关闭时释放资源
    """
    global _connection
    # 如果连接存在且未关闭，则关闭
    if _connection is not None and not _connection.is_closed:
        await _connection.close()
    # 置空，便于下次重新创建
    _connection = None


# ============================================================
# 2. 任务通道和交换器声明
# ============================================================

async def _task_channel() -> tuple[AbstractChannel, aio_pika.abc.AbstractExchange]:
    """
    创建任务通道并声明交换器/队列/绑定。
    
    这是 Worker 和 API 共同使用的底层基础设施：
        1. 获取全局连接
        2. 创建通道（Channel）
        3. 设置 prefetch=1（一次只取一条消息，避免单 Worker 过载）
        4. 声明 DIRECT 交换器（精确路由）
        5. 声明持久化队列（RabbitMQ 重启不丢失队列定义）
        6. 将队列绑定到交换器，绑定 5 个路由键（对应 5 种任务类型）
    
    返回：
        tuple: (通道对象, 交换器对象)
    
    注意：
        这里的 prefetch=1 是通道级别的默认值，实际并发由 Worker 的 set_qos 覆盖
    """
    # 1. 获取全局连接
    conn = await get_connection()
    # 2. 创建通道（一个连接可以有多个通道）
    channel = await conn.channel()
    # 3. 设置 QoS：一次最多取 10 条未确认的消息
    await channel.set_qos(prefetch_count=10)
    
    # 4. 声明任务交换器（DIRECT 类型，持久化）
    exchange = await channel.declare_exchange(
        TASK_EXCHANGE,          # 交换器名：gameforge.tasks
        ExchangeType.DIRECT,    # DIRECT：精确匹配 routing_key
        durable=True            # 持久化：RabbitMQ 重启不丢失
    )
    
    # 5. 声明任务队列（持久化）
    queue = await channel.declare_queue(
        TASK_QUEUE,             # 队列名：gameforge.worker
        durable=True            # 持久化
    )
    
    # 6. 绑定队列到交换器：将 5 个路由键绑定到队列
    #    这样发送到 gameforge.tasks 交换器、routing_key 匹配的消息
    #    都会被路由到 gameforge.worker 队列
    for rk in (
        TASK_EXECUTE_RUN,          # "execute_run"
        TASK_RESUME_RUN,           # "resume_run"
        TASK_SEND_VERIFICATION,    # "send_verification_email"
        TASK_SEND_RESET,           # "send_reset_email"
        TASK_SEND_NOTIFICATION,    # "send_notification_email"
    ):
        await queue.bind(exchange, routing_key=rk)
    
    return channel, exchange


async def _ws_exchange(channel: AbstractChannel) -> aio_pika.abc.AbstractExchange:
    """
    声明 WebSocket 事件交换器（TOPIC 类型）。
    
    用于 Worker 向前端推送实时进度（游戏生成状态、LLM 调用过程等）。
    
    参数：
        channel: RabbitMQ 通道对象
    
    返回：
        AbstractExchange: WebSocket 交换器对象
    
    注意：
        durable=False 表示交换器不持久化（重启后丢失，但代码会自动重建）
    """
    return await channel.declare_exchange(
        WS_EXCHANGE,            # 交换器名：gameforge.ws
        ExchangeType.TOPIC,     # TOPIC：支持通配符匹配（如 run.*）
        durable=False           # 不持久化（临时交换器）
    )


# ============================================================
# 3. 任务发布器（生产者）
# ============================================================

class RabbitTaskPublisher:
    """
    RabbitMQ 任务发布器。
    
    职责：API 服务用它来发送任务消息到 RabbitMQ。
    
    使用示例：
        publisher = RabbitTaskPublisher()
        await publisher.publish(TASK_EXECUTE_RUN, {"run_id": run_id})
    
    设计要点：
        1. 懒加载：第一次 publish 时才创建通道
        2. 复用通道：一个实例只使用一个通道
        3. 持久化消息：防止 RabbitMQ 重启丢失任务
    """
    
    # 缓存交换器对象（懒加载）
    _exchange: aio_pika.abc.AbstractExchange | None = None
    # 缓存通道对象（懒加载）
    _channel: AbstractChannel | None = None

    async def _ensure(self) -> aio_pika.abc.AbstractExchange:
        """
        确保交换器已初始化（懒加载）。
        
        第一次调用时创建通道和交换器，后续复用。
        
        返回：
            AbstractExchange: 任务交换器对象
        """
        if self._exchange is None:
            # 创建任务通道（包含交换器声明和队列绑定）
            self._channel, self._exchange = await _task_channel()
        return self._exchange

    async def publish(self, task: str, payload: dict[str, Any]) -> None:
        """
        发布一个任务到 RabbitMQ。
        
        参数：
            task: 任务类型（如 'execute_run'）
            payload: 任务参数（如 {'run_id': 'abc-123'}）
        
        执行流程：
            1. 确保通道和交换器已创建
            2. 使用 encode_task 打包消息
            3. 设置 delivery_mode=PERSISTENT（持久化）
            4. 用 task 作为 routing_key 发布
        
        注意：
            如果 RabbitMQ 断开，connect_robust 会自动重连
        """
        # 1. 确保交换器已初始化
        exchange = await self._ensure()
        
        # 2. 发布消息
        await exchange.publish(
            Message(
                # 3. 编码消息：{"task": "...", "payload": {...}}
                body=encode_task(task, payload),
                # 4. 持久化：消息写入磁盘，RabbitMQ 重启不丢失
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            # 5. routing_key 等于 task 名
            routing_key=task,
        )


# ============================================================
# 4. WebSocket 事件总线（实时推送）
# ============================================================

class RabbitWsBus:
    """
    RabbitMQ WebSocket 事件总线。
    
    职责：通过 RabbitMQ 的 TOPIC 交换器，实现 Worker → 前端 的实时推送。
    
    使用场景：
        - 游戏生成进度推送（策划完成、代码生成中、QA 通过等）
        - 每个 run_id 对应一个独立的路由键
    
    路由规则：
        - 发布：发送到 gameforge.ws 交换器，routing_key = f"run.{run_id}"
        - 订阅：绑定到 routing_key = f"run.{run_id}"，只接收该 run 的事件
    """

    async def publish(
        self, run_id: uuid.UUID, event_type: WSEventType, payload: dict
    ) -> None:
        """
        发布一个 WebSocket 事件。
        
        参数：
            run_id: 运行实例的 UUID（用于路由）
            event_type: 事件类型（如 'planning_completed'）
            payload: 事件数据
        
        示例：
            await ws_bus.publish(
                run_id,
                WSEventType.PLANNING_COMPLETED,
                {"plan": "..."}
            )
        """
        # 1. 构造 WSEvent 对象
        ev = WSEvent(
            type=event_type,                    # 事件类型
            run_id=run_id,                      # 运行实例 ID
            ts=datetime.now(UTC),               # 时间戳（UTC）
            payload=payload                     # 事件数据
        )
        # 2. 发布序列化后的 JSON 数据
        await self.publish_data(run_id, ev.model_dump_json())

    async def publish_data(self, run_id: uuid.UUID, data: str) -> None:
        """
        发布原始数据到 WebSocket 交换器。
        
        参数：
            run_id: 运行实例的 UUID
            data: JSON 字符串（已序列化的事件）
        
        注意：
            每次发布创建临时通道，用完即关闭，避免连接泄漏
        """
        # 1. 获取全局连接
        conn = await get_connection()
        # 2. 创建临时通道
        channel = await conn.channel()
        try:
            # 3. 获取 WebSocket 交换器
            exchange = await _ws_exchange(channel)
            # 4. 发布消息到 run.{run_id} 路由键
            await exchange.publish(
                Message(body=data.encode()),
                routing_key=f"run.{run_id}",
            )
        finally:
            # 5. 关闭通道（释放资源）
            await channel.close()

    async def subscribe_queue(
        self, run_id: uuid.UUID
    ) -> tuple[AbstractChannel, AbstractQueue]:
        """
        订阅某个 run_id 的事件队列。
        
        参数：
            run_id: 运行实例的 UUID
        
        返回：
            tuple: (通道对象, 队列对象)
        
        注意：
            队列名称由 RabbitMQ 自动生成（空字符串），
            且设置为 exclusive（独占）和 auto_delete（用完即删）
        """
        # 1. 获取全局连接
        conn = await get_connection()
        # 2. 创建通道
        channel = await conn.channel()
        # 3. 获取 WebSocket 交换器
        exchange = await _ws_exchange(channel)
        # 4. 创建临时队列（独占、自动删除）
        queue = await channel.declare_queue(
            "",                      # 空字符串 → RabbitMQ 自动生成名称
            exclusive=True,          # 独占：只能被当前连接使用
            auto_delete=True         # 自动删除：连接断开后删除队列
        )
        # 5. 绑定队列到交换器，只接收该 run_id 的事件
        await queue.bind(exchange, routing_key=f"run.{run_id}")
        return channel, queue

    async def iter_events(self, run_id: uuid.UUID) -> AsyncIterator[str]:
        """
        迭代接收某个 run_id 的所有 WebSocket 事件。
        
        参数：
            run_id: 运行实例的 UUID
        
        使用示例：
            async for event_json in ws_bus.iter_events(run_id):
                data = json.loads(event_json)
                # 处理事件...
        
        注意：
            退出时自动关闭通道，释放资源
        """
        # 1. 订阅该 run_id 的事件队列
        channel, queue = await self.subscribe_queue(run_id)
        try:
            # 2. 创建异步迭代器，持续接收消息
            async with queue.iterator() as it:
                async for message in it:
                    # 3. 处理消息（自动确认）
                    async with message.process():
                        # 4. 解码并返回 JSON 字符串
                        yield message.body.decode()
        finally:
            # 5. 清理：关闭通道
            await channel.close()


# ============================================================
# 5. 工具函数
# ============================================================

async def ping_rabbitmq() -> bool:
    """
    健康检查：测试 RabbitMQ 是否可达。
    
    使用场景：
        - /ready 健康检查端点
        - 容器编排（Kubernetes）的就绪探针
    
    返回：
        bool: True 表示连接正常，False 表示连接失败
    """
    try:
        # 尝试连接 RabbitMQ
        conn = await aio_pika.connect_robust(settings.rabbitmq_url)
        # 关闭连接
        await conn.close()
        return True
    except Exception:
        # 连接失败
        return False


async def task_queue_stats() -> dict[str, int | str | None]:
    """
    获取任务队列的统计信息（开发/调试用）。
    
    返回：
        dict: {
            "queue": "gameforge.worker",   # 队列名
            "messages": 0,                 # 队列中的消息数
            "consumers": 1                 # 正在消费的 Worker 数
        }
    
    使用场景：
        - /api/v1/dev/queue/stats 调试端点
        - 监控队列积压情况
    """
    # 1. 创建任务通道
    channel, _exchange = await _task_channel()
    try:
        # 2. 被动声明队列（不创建，只获取信息）
        queue = await channel.declare_queue(TASK_QUEUE, durable=True, passive=True)
        # 3. 获取声明结果（包含统计信息）
        decl = queue.declaration_result
        return {
            "queue": TASK_QUEUE,
            "messages": int(decl.message_count or 0),   # 积压消息数
            "consumers": int(decl.consumer_count or 0), # 消费者数量
        }
    finally:
        # 4. 关闭通道
        await channel.close()


async def purge_task_queue() -> int:
    """
    清空任务队列中的所有消息（开发/调试用）。
    
    返回：
        int: 被清空的消息数量
    
    使用场景：
        - 测试环境重置数据
        - 清理积压的无效任务
    
    注意：
        仅用于开发环境，生产环境慎用！
    """
    # 1. 创建任务通道
    channel, _exchange = await _task_channel()
    try:
        # 2. 声明队列（持久化）
        queue = await channel.declare_queue(TASK_QUEUE, durable=True)
        # 3. 清空队列
        result = await queue.purge()
        # 4. 返回被清空的消息数
        return int(result.message_count if result is not None else 0)
    finally:
        # 5. 关闭通道
        await channel.close()