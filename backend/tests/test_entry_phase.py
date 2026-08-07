"""Batch B · B-B2: entry_phase smart routing."""

import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.enums import EntryPhase
from app.forge.entry_router import classify_entry_phase
from app.forge.graph import run_generation
from app.forge.runner import execute_run


@pytest.mark.parametrize(
    ("req", "expected"),
    [
        ("把背景改成紫色", EntryPhase.CODE),
        ("调整分数显示文案", EntryPhase.CODE),
        ("重写核心玩法并增加 Boss 关", EntryPhase.PLAN),
        ("加入加速道具", EntryPhase.PLAN),
    ],
)
def test_classify_entry_phase_with_prior(req: str, expected: EntryPhase) -> None:
    assert classify_entry_phase(req, has_prior_version=True) == expected


def test_classify_entry_phase_first_run() -> None:
    assert classify_entry_phase("任意需求", has_prior_version=False) == EntryPhase.PLAN


async def test_create_run_small_change_entry_code(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    db_session,
) -> None:
    r = await verified_client.post(
        "/api/v1/games",
        json={"title": "测试", "requirement": "做一个贪吃蛇"},
    )
    gid = uuid.UUID(r.json()["data"]["game_id"])
    # 先跑一版产生 v1 + design_doc
    run1 = await verified_client.post(
        f"/api/v1/games/{gid}/runs",
        json={"requirement": "初始版本"},
    )
    rid1 = uuid.UUID(run1.json()["data"]["run_id"])
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid1)
    await run_generation(ctx, rid1, resume=True, decision="approve")

    run2 = await verified_client.post(
        f"/api/v1/games/{gid}/runs",
        json={"requirement": "把背景颜色改成深紫色"},
    )
    assert run2.status_code == 201, run2.text
    body = run2.json()["data"]
    assert body["entry_phase"] == "code"
    assert body["phase"] == "code"

    rid2 = uuid.UUID(body["run_id"])
    await execute_run(ctx, rid2)
    st = await verified_client.get(f"/api/v1/runs/{rid2}")
    data = st.json()["data"]
    assert data["entry_phase"] == "code"
    assert data.get("current_hitl") != {"node": "plan_confirm"}
