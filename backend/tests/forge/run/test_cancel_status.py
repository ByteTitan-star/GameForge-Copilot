"""Cancel 应落成独立终态 cancelled，且不复活。"""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import httpx

from app.core import db
from app.enums import RunStatus
from app.forge.graph import run_generation
from app.models.generation_run import GenerationRun


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json={"title": "取消状态测试", "requirement": "x"})
    return uuid.UUID(r.json()["data"]["game_id"])


async def _run_status(rid: uuid.UUID) -> str:
    async with db.SessionLocal() as s:
        run = await s.get(GenerationRun, rid)
        assert run is not None
        return run.status


async def test_cancel_sets_cancelled_status(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid = await _make_game(verified_client)
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )
    cancelled = await verified_client.post(f"/api/v1/runs/{rid}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == RunStatus.CANCELLED.value
    assert await _run_status(rid) == RunStatus.CANCELLED.value

    await run_generation({"redis": redis_client}, rid, resume=True, decision="approve")
    assert await _run_status(rid) == RunStatus.CANCELLED.value
