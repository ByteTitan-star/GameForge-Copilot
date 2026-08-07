"""生成进度 WS：query token 鉴权 + owner/admin 校验 + RabbitMQ topic 转发。

docs/06：浏览器原生 WS 不能设自定义头，token 走 `?token=`；access 过期则拒接。
WS 不进 OpenAPI（契约 docs/10 §5）。
"""

import asyncio
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


async def _replay_buffered(ws: WebSocket, run_id: uuid.UUID) -> None:
    for data in await list_events_auto(run_id):
        await ws.send_text(data)


async def _relay_memory(ws: WebSocket, run_id: uuid.UUID) -> None:
    bus = get_ws_bus()
    async for data in bus.iter_events(run_id):
        await ws.send_text(data)


async def _relay_rabbit(ws: WebSocket, run_id: uuid.UUID) -> None:
    bus = get_ws_bus()
    channel, queue = await bus.subscribe_queue(run_id)
    try:
        async with queue.iterator() as it:
            async for message in it:
                async with message.process():
                    await ws.send_text(message.body.decode())
    finally:
        await channel.close()


async def _await_disconnect(ws: WebSocket) -> None:
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return


@router.websocket("/runs/{run_id}")
async def run_ws(websocket: WebSocket, run_id: uuid.UUID) -> None:
    """握手用短命 DB 会话（鉴权+owner），订阅前释放，避免 WS 长连占用 DB 连接。"""
    async with db_module.SessionLocal() as s:
        user = await _ws_user(s, websocket.query_params.get("token"))
        if user is None:
            await websocket.close(code=4401)
            return
        run = await s.get(GenerationRun, run_id)
        authorized = run is not None and (
            run.user_id == user.id or user.role == Role.ADMIN.value
        )
    if not authorized:
        await websocket.close(code=4403)
        return

    await websocket.accept()
    await _replay_buffered(websocket, run_id)
    relay_fn = _relay_memory if use_memory() else _relay_rabbit
    relay = asyncio.create_task(relay_fn(websocket, run_id))
    disc = asyncio.create_task(_await_disconnect(websocket))
    try:
        _done, pending = await asyncio.wait({relay, disc}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    finally:
        relay.cancel()
