"""M4 WS 事件流：memory/RabbitMQ 总线 + 鉴权拒接 + relay 单测。"""

import asyncio
import json
import uuid

import httpx
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.enums import WSEventType
from app.forge.events import publish_event
from app.main import app
from app.messaging.factory import get_ws_bus
from app.ws.runs import _relay_memory

_GAME = {"title": "贪吃蛇", "requirement": "方向键"}
_RUN = {"requirement": "加速道具"}


async def _make_run(verified_client: httpx.AsyncClient) -> uuid.UUID:
    r = await verified_client.post("/api/v1/games", json=_GAME)
    gid = r.json()["data"]["game_id"]
    r = await verified_client.post(f"/api/v1/games/{gid}/runs", json=_RUN)
    return uuid.UUID(r.json()["data"]["run_id"])


async def test_bus_roundtrip() -> None:
    rid = uuid.uuid4()
    bus = get_ws_bus()
    q = bus.subscribe(rid)
    await publish_event(rid, WSEventType.PHASE_START, {"phase": "plan"})
    data = await asyncio.wait_for(q.get(), timeout=1.0)
    ev = json.loads(data)
    assert ev["type"] == "phase_start"
    assert ev["run_id"] == str(rid)
    assert ev["payload"]["phase"] == "plan"
    bus.unsubscribe(rid, q)


async def test_ws_rejects_no_token(verified_client: httpx.AsyncClient) -> None:
    rid = await _make_run(verified_client)
    with TestClient(app) as c, pytest.raises(WebSocketDisconnect), \
            c.websocket_connect(f"/ws/runs/{rid}") as ws:
        ws.receive_text()


async def test_ws_rejects_non_owner(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    rid = await _make_run(verified_client)
    other_token = auth_client.headers["Authorization"].split(" ", 1)[1]
    with TestClient(app) as c, pytest.raises(WebSocketDisconnect), \
            c.websocket_connect(f"/ws/runs/{rid}?token={other_token}") as ws:
        ws.receive_text()


async def test_relay_forwards() -> None:
    """_relay_memory 把总线消息发到 ws.send_text。"""
    rid = uuid.uuid4()

    class _FakeWS:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_text(self, data: str) -> None:
            self.sent.append(data)

    fake = _FakeWS()
    task = asyncio.create_task(_relay_memory(fake, rid))
    await asyncio.sleep(0.05)
    await publish_event(rid, WSEventType.PHASE_START, {"phase": "plan"})
    await asyncio.sleep(0.05)
    task.cancel()
    assert fake.sent, "relay 未转发任何消息"
    ev = json.loads(fake.sent[0])
    assert ev["type"] == "phase_start"
    assert ev["run_id"] == str(rid)
