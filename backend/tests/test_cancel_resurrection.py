"""取消 run 后，worker 残留/重投的 resume 消息不得将其复活（run_generation 终态守卫）。

复现用户反馈：HITL 等待中点「终止」后，worker 仍在消费该 run。
根因是 run_generation 入口不校验状态，resume 分支无条件把 FAILED 改回 RUNNING。
"""

import uuid

import fakeredis.aioredis
import httpx

from app.core import db
from app.enums import RunStatus
from app.forge.graph import run_generation
from app.models.generation_run import GenerationRun


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post(
        "/api/v1/games", json={"title": "取消复活测试", "requirement": "x"}
    )
    return uuid.UUID(r.json()["data"]["game_id"])


async def _run_status(rid: uuid.UUID) -> str:
    async with db.SessionLocal() as s:
        run = await s.get(GenerationRun, rid)
        assert run is not None
        return run.status


async def test_cancelled_run_not_resurrected_by_resume(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """已 cancel（FAILED）的 run，worker 再消费 resume 消息时应被入口守卫跳过。"""
    gid = await _make_game(verified_client)
    rid = uuid.UUID(
        (
            await verified_client.post(
                f"/api/v1/games/{gid}/runs", json={"requirement": "x"}
            )
        ).json()["data"]["run_id"]
    )

    # 终止 run（RUNNING → FAILED，ended_at 置位，checkpoint/control 清空）
    cancelled = await verified_client.post(f"/api/v1/runs/{rid}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["status"] == RunStatus.FAILED.value

    # 模拟 worker 消费到一条针对该 run 的残留 resume 消息
    ctx = {"redis": redis_client}
    await run_generation(ctx, rid, resume=True, decision="approve")

    # 守卫应直接跳过：run 不得被改回 RUNNING
    assert await _run_status(rid) == RunStatus.FAILED.value
