"""生成进度 WS：query token 鉴权 + owner/admin 校验 + RabbitMQ topic 转发。

docs/06：浏览器原生 WS 不能设自定义头，token 走 `?token=`；access 过期则拒接。
WS 不进 OpenAPI（契约 docs/10 §5）。
"""

import asyncio
import contextlib
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.core import db as db_module
from app.enums import Role
from app.forge.event_log import list_events_auto
from app.messaging.factory import get_ws_bus, use_memory
from app.models.generation_run import GenerationRun
from app.models.user import User

router = APIRouter(prefix="/ws", tags=["ws"])


async def _ws_user(db: AsyncSession, token: str | None) -> User | None:
    """从 query token 解析并加载当前用户。

    场景：WS 握手鉴权（浏览器无法设 Authorization 头）。
    参数：db、token - access JWT。
    返回：User 或 None（无效/过期）。
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    if payload.get("type") != "access":
        return None
    try:
        uid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None
    return await db.get(User, uid)


async def _replay_buffered(ws: WebSocket, run_id: uuid.UUID, after: int | None) -> None:
    """重放 run 历史事件到 WebSocket（after 游标之后）。

    场景：客户端带 ?after= 重连时补发漏收事件。
    参数：ws、run_id、after - 事件序号游标。
    """
    for data in await list_events_auto(run_id, after):
        await ws.send_text(data)


async def _relay_memory(
    ws: WebSocket,
    run_id: uuid.UUID,
    ready: asyncio.Event | None = None,
    replayed: asyncio.Event | None = None,
) -> None:
    """memory 模式下将 run 事件从内存队列转发到 WebSocket。

    场景：pytest 或 messaging_backend=memory。
    参数：ws、run_id、ready/replayed - 与回放握手的 Event。
    """
    from app.messaging.memory import MemoryWsBus

    bus = get_ws_bus()
    assert isinstance(bus, MemoryWsBus)
    queue = bus.subscribe(run_id)
    if ready is not None:
        ready.set()
    try:
        if replayed is not None:
            await replayed.wait()
        while True:
            await ws.send_text(await queue.get())
    finally:
        bus.unsubscribe(run_id, queue)


async def _relay_rabbit(
    ws: WebSocket,
    run_id: uuid.UUID,
    ready: asyncio.Event | None = None,
    replayed: asyncio.Event | None = None,
) -> None:
    """RabbitMQ 模式下订阅 run topic 并转发消息到 WebSocket。

    场景：生产环境 messaging_backend=rabbit。
    参数：ws、run_id、ready/replayed - 与回放握手的 Event。
    """
    from app.messaging.rabbit import RabbitWsBus

    bus = get_ws_bus()
    assert isinstance(bus, RabbitWsBus)
    channel = None
    try:
        channel, queue = await bus.subscribe_queue(run_id)
        if ready is not None:
            ready.set()
        if replayed is not None:
            await replayed.wait()
        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    await ws.send_text(message.body.decode())
    finally:
        if ready is not None:
            ready.set()
        if channel is not None:
            await channel.close()


async def _await_disconnect(ws: WebSocket) -> None:
    """阻塞直到客户端断开 WebSocket 连接。

    场景：与 relay 协程并行，任一结束即取消另一方。
    参数：ws - 已 accept 的连接。
    """
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return


@router.websocket("/runs/{run_id}")
async def run_ws(websocket: WebSocket, run_id: uuid.UUID) -> None:
    """Run 进度 WebSocket：鉴权、历史回放、实时事件转发。

    场景：GET /ws/runs/{run_id}?token=&after=。
    参数：websocket、run_id。
    返回：无（长连接直至断开）。
    """
    async with db_module.SessionLocal() as s:
        user = await _ws_user(s, websocket.query_params.get("token"))
        if user is None:
            await websocket.close(code=4401)
            return
        run = await s.get(GenerationRun, run_id)
        authorized = run is not None and (run.user_id == user.id or user.role == Role.ADMIN.value)
    if not authorized:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    try:
        after = int(websocket.query_params.get("after", "0"))
    except ValueError:
        after = 0
    relay_fn = _relay_memory if use_memory() else _relay_rabbit
    ready = asyncio.Event()
    replayed = asyncio.Event()
    relay = asyncio.create_task(relay_fn(websocket, run_id, ready, replayed))
    try:
        await ready.wait()
        await _replay_buffered(websocket, run_id, after)
        replayed.set()
        disc = asyncio.create_task(_await_disconnect(websocket))
        try:
            _done, pending = await asyncio.wait({relay, disc}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
        finally:
            disc.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await disc
    finally:
        relay.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay
