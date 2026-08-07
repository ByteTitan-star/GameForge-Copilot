"""Run 失败重试（Batch A · B-A5）。"""

import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.forge import state as ckpt
from app.forge.graph import run_generation
from app.forge.runner import execute_run


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post(
        "/api/v1/games", json={"title": "重试测试", "requirement": "测试 retry"}
    )
    return uuid.UUID(r.json()["data"]["game_id"])


async def test_retry_run_from_qa_failed(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.sandbox.playtest import PlaytestResult

    async def _fail(_html: str) -> PlaytestResult:
        return PlaytestResult(ok=False, errors=["mock"], console_logs=[])

    monkeypatch.setattr("app.forge.graph.run_playtest", _fail)
    from app.core.config import settings

    monkeypatch.setattr(settings, "qa_max_retries", 0)

    gid = await _make_game(verified_client)
    rid = uuid.UUID(
        (
            await verified_client.post(
                f"/api/v1/games/{gid}/runs", json={"requirement": "x"}
            )
        ).json()["data"]["run_id"]
    )
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)
    await run_generation(ctx, rid, resume=True, decision="approve")

    st = await ckpt.load_state(redis_client, rid)
    assert st is not None
    assert st.get("phase") == "qa_failed"

    r = await verified_client.post(f"/api/v1/runs/{rid}/retry")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "running"
    assert r.json()["data"]["phase"] == "code"


async def test_retry_run_invalid_state(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid = await _make_game(verified_client)
    rid = uuid.UUID(
        (
            await verified_client.post(
                f"/api/v1/games/{gid}/runs", json={"requirement": "x"}
            )
        ).json()["data"]["run_id"]
    )
    r = await verified_client.post(f"/api/v1/runs/{rid}/retry")
    assert r.status_code == 409
