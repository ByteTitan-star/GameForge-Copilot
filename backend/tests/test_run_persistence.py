"""Run 事件缓冲与 active runs API。"""

import json
import uuid

import httpx
from starlette.testclient import TestClient

from app.enums import WSEventType
from app.forge.events import publish_event
from app.main import app

_GAME = {"title": "贪吃蛇", "requirement": "方向键"}
_RUN = {"requirement": "加速道具"}


async def _make_run(verified_client: httpx.AsyncClient) -> uuid.UUID:
    r = await verified_client.post("/api/v1/games", json=_GAME)
    gid = r.json()["data"]["game_id"]
    r = await verified_client.post(f"/api/v1/games/{gid}/runs", json=_RUN)
    return uuid.UUID(r.json()["data"]["run_id"])


async def test_run_events_buffered_and_replayable(
    verified_client: httpx.AsyncClient,
) -> None:
    rid = await _make_run(verified_client)
    await publish_event(rid, WSEventType.PHASE_START, {"phase": "plan"})
    await publish_event(rid, WSEventType.TOOL_CALL, {"phase": "plan", "summary": "ok"})

    r = await verified_client.get(f"/api/v1/runs/{rid}/events")
    assert r.status_code == 200, r.text
    events = r.json()["data"]
    assert len(events) >= 2
    assert events[0]["type"] == "phase_start"
    assert events[-1]["type"] == "tool_call"


async def test_ws_replays_buffered_events(verified_client: httpx.AsyncClient) -> None:
    rid = await _make_run(verified_client)
    await publish_event(rid, WSEventType.PHASE_START, {"phase": "art"})

    token = verified_client.headers["Authorization"].split(" ", 1)[1]
    with TestClient(app) as c, c.websocket_connect(
        f"/ws/runs/{rid}?token={token}"
    ) as ws:
        first = json.loads(ws.receive_text())
        assert first["type"] == "phase_start"
        assert first["payload"]["phase"] == "art"


async def test_list_active_runs(verified_client: httpx.AsyncClient) -> None:
    rid = await _make_run(verified_client)
    r = await verified_client.get("/api/v1/me/runs/active")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert any(row["run_id"] == str(rid) for row in rows)


async def test_get_run_includes_hitl_wait_from_checkpoint(
    verified_client: httpx.AsyncClient,
    redis_client,
) -> None:
    from app.core import db as db_module
    from app.forge import state as ckpt
    from app.models.generation_run import GenerationRun

    rid = await _make_run(verified_client)
    async with db_module.SessionLocal() as session:
        run = await session.get(GenerationRun, rid)
        assert run is not None
        run.status = "paused"
        await ckpt.save_state(
            redis_client,
            rid,
            {
                "phase": "plan_confirm",
                "design_doc": {"title": "T", "gameplay": "g", "controls": "c", "levels": []},
            },
            session,
        )
        await session.commit()
    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["hitl_wait"]["node"] == "plan_confirm"
    assert body["hitl_wait"]["design_doc"]["title"] == "T"


async def test_get_run_hides_stale_hitl_when_run_is_running(
    verified_client: httpx.AsyncClient,
    redis_client,
) -> None:
    from app.forge import state as ckpt

    rid = await _make_run(verified_client)
    await ckpt.save_state(
        redis_client,
        rid,
        {"phase": "plan_confirm", "design_doc": {"title": "stale"}},
    )
    response = await verified_client.get(f"/api/v1/runs/{rid}")
    body = response.json()["data"]
    assert body["status"] == "running"
    assert body["current_hitl"] is None
    assert body["hitl_wait"] is None
