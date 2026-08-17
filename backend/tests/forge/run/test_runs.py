"""M4/M6 runs：发起 run + 列表 + 状态 + 全生成链（HITL 中断→resume→done）。"""

import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.core import db as db_module
from app.forge import state as ckpt
from app.forge.graph import run_generation
from app.forge.runner import execute_run

GAME_BODY = {"title": "贪吃蛇", "requirement": "方向键"}
RUN_BODY = {"requirement": "加入加速道具"}


async def _grant_resume(
    redis_client: fakeredis.aioredis.FakeRedis,
    run_id: uuid.UUID,
    decision: str = "approve",
    modify_text: str | None = None,
) -> None:
    """模拟合法入口（resolve_hitl / resume / retry）写入的一次性推进凭据。

    生产路径由 app.forge.queue.enqueue_resume 写入；测试直接调 run_generation
    绕过该入口，故手动预置，否则 _run_body 会按陈旧消息跳过。
    """
    async with db_module.SessionLocal() as s:
        st = await ckpt.load_state(redis_client, run_id, s) or {}
        granted = {
            **st,
            "resume_grant": {"decision": decision, "modify_text": modify_text},
        }
        await ckpt.save_state(redis_client, run_id, granted, s)
        await s.commit()


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=GAME_BODY)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_run(client: httpx.AsyncClient, gid: uuid.UUID) -> uuid.UUID:
    r = await client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["run_id"])


async def test_create_run_non_owner_404(
    verified_client: httpx.AsyncClient, client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    """另一已验证用户对非自己 game 发起 run → 404（不泄露存在）。"""
    gid = await _make_game(verified_client)
    # 第二个用户 b@b.com：注册→验证→登录（已验证才能穿过门禁到达 owner 检查）
    await client.post("/api/v1/auth/register", json={"email": "b@b.com", "password": "password123"})
    code = sent["verify:b@b.com"]
    r = await client.post("/api/v1/auth/verify-email", json={"email": "b@b.com", "code": code})
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
    """策划确认→美术方向确认→详细美术稿→code/qa→done。"""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)

    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)

    # 首次跑到 HITL 中断：状态 paused/plan，current_hitl=plan_confirm
    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "paused"
    assert d["current_hitl"] == {"node": "plan_confirm"}

    # 策划确认后严格串行进入美术方向 HITL，不应直接编码。
    await _grant_resume(redis_client, rid)
    await run_generation(ctx, rid, resume=True, decision="approve")

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    art_wait = r.json()["data"]
    assert art_wait["status"] == "paused"
    assert art_wait["current_hitl"] == {"node": "art_confirm"}
    assert [item["id"] for item in art_wait["hitl_wait"]["art_options"]["options"]] == [
        "A",
        "B",
    ]

    # 只有选定方向后才生成详细美术稿并进入代码阶段。
    await _grant_resume(redis_client, rid, "select_a")
    await run_generation(ctx, rid, resume=True, decision="select_a")

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "done"
    assert d["phase"] == "done"
    assert d["current_hitl"] is None

    r = await verified_client.get(f"/api/v1/games/{gid}/versions")
    versions = r.json()["data"]
    assert len(versions) == 1 and versions[0]["version"] == 1

    r = await verified_client.get(f"/draft/{gid}/1")
    assert r.status_code == 200 and "canvas" in r.text


async def test_stale_resume_without_grant_is_skipped(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """HITL 等待态下，没有 resume_grant 的陈旧 resume 必须被跳过，run 不自动推进。

    钉死 app.forge.graph._run_body 的 stale-skip 分支：at-least-once 投递下的旧
    resume 消息读不到凭据，在 plan_confirm 直接 return，堵住「用户没点确认 art/code
    却自己跑起来」。合法入口（resolve_hitl/resume/retry）由 enqueue_resume 写 grant，
    测试里用 _grant_resume 模拟；本用例刻意不写，验证拦截。
    """
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)

    # 首次跑到 HITL 中断：paused/plan，current_hitl=plan_confirm
    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.json()["data"]["status"] == "paused"
    assert r.json()["data"]["current_hitl"] == {"node": "plan_confirm"}

    # 不预置 grant，直接 resume（模拟陈旧消息重投）
    await run_generation(ctx, rid, resume=True, decision="approve")

    # 仍停在 HITL：未推进到 art，未产生版本
    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "paused"
    assert d["phase"] == "plan"
    assert d["current_hitl"] == {"node": "plan_confirm"}

    r = await verified_client.get(f"/api/v1/games/{gid}/versions")
    assert r.json()["data"] == []


async def test_grant_consumed_after_done_prevents_replay(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """resume 跑到 done 后，重投同一条 resume 消息被终态守卫跳过，不产生副作用。

    钉死 run_generation 的终态守卫（status=DONE 直接 return）：grant 在第一次 resume
    被 pop 消费，done_node 又 clear_state；消息重投时既无 grant 也已是终态。
    """
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)
    await _grant_resume(redis_client, rid)
    await run_generation(ctx, rid, resume=True, decision="approve")
    await _grant_resume(redis_client, rid, "select_a")
    await run_generation(ctx, rid, resume=True, decision="select_a")

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.json()["data"]["status"] == "done"
    r = await verified_client.get(f"/api/v1/games/{gid}/versions")
    versions_after_done = r.json()["data"]
    assert len(versions_after_done) == 1

    # 模拟消息重投：再次 resume，终态守卫应直接跳过，版本数不增长
    await run_generation(ctx, rid, resume=True, decision="approve")
    r = await verified_client.get(f"/api/v1/games/{gid}/versions")
    assert r.json()["data"] == versions_after_done


async def test_qa_playtest_failure_retries_then_pauses(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """QA 试玩失败 → CodeQaLoop 修复；预算耗尽后 PAUSED（qa_failed HITL）。"""
    from app.sandbox.playtest import PlaytestResult

    calls = {"n": 0}

    async def _fail_playtest(_html: str, **_kwargs: object) -> PlaytestResult:
        calls["n"] += 1
        return PlaytestResult(
            ok=False,
            errors=["mock js error"],
            console_logs=["err"],
            failure_kind="product",
        )

    monkeypatch.setattr("app.forge.code_qa_exec.run_playtest", _fail_playtest)
    from app.core.config import settings

    monkeypatch.setattr(settings, "code_qa_max_attempts", 1)

    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)
    await _grant_resume(redis_client, rid)
    await run_generation(ctx, rid, resume=True, decision="approve")
    await _grant_resume(redis_client, rid, "select_a")
    await run_generation(ctx, rid, resume=True, decision="select_a")

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.json()["data"]["status"] == "paused"
    assert r.json()["data"]["current_hitl"] is not None
    assert r.json()["data"]["current_hitl"]["node"] == "qa_failed"
    assert calls["n"] >= 1


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


async def test_art_options_retry_exhaustion_falls_back_and_finishes(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """美术 Agent 连续失败时使用内置素材，不把可恢复问题升级为 run 失败。"""
    from app.core.config import settings
    from app.llm import client as llm_client

    calls = {"art": 0}

    async def fail_art_options(*args, **kwargs):
        system = args[4]
        if "方向提案" in system:
            calls["art"] += 1
            from app.enums import LLMProvider
            from app.llm.provider import LLMCompletion, Usage

            return LLMCompletion(content="not-json", usage=Usage(1, 1)), LLMProvider.ANTHROPIC
        return await _fake_llm(*args, **kwargs)

    async def fail_art_options_stream(*args, **kwargs):
        # art 节点切流式后走 call_llm_stream；匹配方向提案让连续失败触发重试耗尽兜底。
        system = args[4]
        if "方向提案" in system:
            calls["art"] += 1
            from app.llm.provider import StreamChunk, Usage

            yield StreamChunk(delta="not-json", usage=None)
            yield StreamChunk(delta="", usage=Usage(1, 1))
            return
        # 非 art 方向提案节点：用原非流式 mock 拿内容，切块 yield，保证 run 正常完成
        result, _prov = await _fake_llm(*args, **kwargs)
        from app.llm.provider import StreamChunk, Usage

        content = result.content
        for i in range(0, len(content), 10):
            yield StreamChunk(delta=content[i : i + 10], usage=None)
        yield StreamChunk(delta="", usage=Usage(10, 5))

    monkeypatch.setattr(settings, "art_max_retries", 2)
    monkeypatch.setattr(llm_client, "call_llm", fail_art_options)
    monkeypatch.setattr(llm_client, "call_llm_stream", fail_art_options_stream)
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)
    await _grant_resume(redis_client, rid)
    await run_generation(ctx, rid, resume=True, decision="approve")

    run = (await verified_client.get(f"/api/v1/runs/{rid}")).json()["data"]
    assert calls["art"] == 2
    assert run["status"] == "done"
    versions = (await verified_client.get(f"/api/v1/games/{gid}/versions")).json()["data"]
    assert len(versions) == 1


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
