"""M4/M6 runs：发起 run + 列表 + 状态 + 全生成链（HITL 中断→resume→done）。"""

import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.forge.graph import run_generation
from app.forge.runner import execute_run
from app.llm.provider import Usage

GAME_BODY = {"title": "贪吃蛇", "requirement": "方向键"}
RUN_BODY = {"requirement": "加入加速道具"}


@pytest.fixture
def _fake_llm(monkeypatch: pytest.MonkeyPatch):
    """mock call_llm：code 阶段返 HTML，其余返桩文本。"""

    async def _fake(db, r, user_id, config_id, system, user_msg):
        if "HTML5" in system:
            return "<html><body><h1>stub game</h1></body></html>", Usage(20, 10)
        if "质检" in system or "PASSED" in system or "FAILED" in system:
            return "PASSED\n全部通过", Usage(5, 3)
        return "stub design doc", Usage(10, 5)

    from app.llm import client as llm_client

    monkeypatch.setattr(llm_client, "call_llm", _fake)
    return _fake


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=GAME_BODY)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_run(client: httpx.AsyncClient, gid: uuid.UUID) -> uuid.UUID:
    r = await client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["run_id"])


async def test_create_run_requires_verified(
    verified_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    gid = await _make_game(verified_client)
    r = await auth_client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 403


async def test_create_run_non_owner_404(
    verified_client: httpx.AsyncClient, client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    """已验证的另一用户对非自己 game 发起 run → 404（不泄露存在）。"""
    gid = await _make_game(verified_client)
    # 第二个已验证用户 b@b.com
    await client.post(
        "/api/v1/auth/register", json={"email": "b@b.com", "password": "password123"}
    )
    vtoken = sent["verify:b@b.com"]
    r = await client.post(
        "/api/v1/auth/verify-email", json={"email": "b@b.com", "code": vtoken}
    )
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/auth/login", json={"email": "b@b.com", "password": "password123"}
    )
    client.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"

    r = await client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "GAME_NOT_FOUND"


async def test_create_list_get_run(verified_client: httpx.AsyncClient) -> None:
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)

    r = await verified_client.get(f"/api/v1/games/{gid}/runs")
    assert r.status_code == 200
    assert any(run["run_id"] == str(rid) for run in r.json()["data"])

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "running"
    assert d["phase"] == "plan"
    assert d["ws_url"] == f"/ws/runs/{rid}"


async def test_full_generation_with_hitl(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """execute_run→plan→HITL 中断；resume→art/code/qa→done + version + /draft 200。"""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)

    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)

    # 首次跑到 HITL 中断：状态 paused/plan，current_hitl=plan_confirm
    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "paused"
    assert d["current_hitl"] == {"node": "plan_confirm"}

    # resume 继续
    await run_generation(ctx, rid, resume=True, decision="approve")

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "done"
    assert d["phase"] == "done"
    assert d["current_hitl"] is None

    r = await verified_client.get(f"/api/v1/games/{gid}/versions")
    versions = r.json()["data"]
    assert len(versions) == 1 and versions[0]["version"] == 1

    r = await verified_client.get(f"/draft/{gid}/1")
    assert r.status_code == 200 and "stub game" in r.text


async def test_hitl_resolve_endpoint(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """POST hitl/resolve 校验 plan_confirm 态 + enqueue resume（noop）+ 200。"""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    await execute_run({"redis": redis_client}, rid)

    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "plan_confirm", "decision": "approve"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["phase"] == "art"


async def test_hitl_resolve_wrong_state_409(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    # 未执行 execute_run → 无检查点状态 → 409
    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "plan_confirm", "decision": "approve"},
    )
    assert r.status_code == 409
