"""ask_user 端到端（ADR-17）：plan 提问暂停 → 回答恢复；预算耗尽自动续答。"""

from __future__ import annotations

import json
import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.core import db as db_module
from app.enums import LLMProvider, RunStatus
from app.forge import state as ckpt
from app.forge.runner import execute_run
from app.llm import client as llm_client
from app.llm.provider import LLMCompletion, StreamChunk, Usage
from app.models.generation_run import GenerationRun

_ASK_JSON = json.dumps(
    {
        "tool": "ask_user",
        "reason": "题材方向决定玩法形态",
        "question": "想要闯关还是生存？",
        "options": ["闯关", "生存"],
    },
    ensure_ascii=False,
)


def _patch_plan_to_ask_once(monkeypatch: pytest.MonkeyPatch) -> dict:
    """首次 plan 调用返回 ask_user 工具 JSON，其余委托 _fake_llm。"""
    base_call = llm_client.call_llm
    base_stream = llm_client.call_llm_stream
    asked = {"n": 0}

    def _hit(system: str) -> LLMCompletion | None:
        if "ask_user 工具" in system and asked["n"] == 0:
            asked["n"] += 1
            return LLMCompletion(content=_ASK_JSON, usage=Usage(5, 2))
        return None

    async def _call(db, r, user_id, config_id, system, user_msg, **kw):
        hit = _hit(system)
        if hit is not None:
            return hit, LLMProvider.ANTHROPIC
        return await base_call(db, r, user_id, config_id, system, user_msg, **kw)

    async def _stream(db, r, user_id, config_id, system, user_msg, **kw):
        hit = _hit(system)
        if hit is not None:
            for i in range(0, len(hit.content), 10):
                yield StreamChunk(delta=hit.content[i : i + 10], usage=None)
            yield StreamChunk(delta="", usage=hit.usage)
            return
        async for chunk in base_stream(db, r, user_id, config_id, system, user_msg, **kw):
            yield chunk

    monkeypatch.setattr(llm_client, "call_llm", _call)
    monkeypatch.setattr(llm_client, "call_llm_stream", _stream)
    return asked


async def _make_game_run(client: httpx.AsyncClient) -> tuple[uuid.UUID, uuid.UUID]:
    game = await client.post("/api/v1/games", json={"title": "ask", "requirement": "做个游戏"})
    gid = uuid.UUID(game.json()["data"]["game_id"])
    run = await client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "做个游戏"})
    assert run.status_code == 201, run.text
    return gid, uuid.UUID(run.json()["data"]["run_id"])


async def test_plan_ask_user_pauses_then_answer_resumes(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked = _patch_plan_to_ask_once(monkeypatch)
    ctx = {"redis": redis_client}
    _gid, rid = await _make_game_run(verified_client)

    await execute_run(ctx, rid)

    async with db_module.SessionLocal() as s:
        st = await ckpt.load_state(redis_client, rid, s) or {}
        run = await s.get(GenerationRun, rid)
        assert st.get("phase") == "agent_question"
        assert st.get("ask_user_count") == 1
        question = st.get("agent_question") or {}
        assert question.get("question") == "想要闯关还是生存？"
        assert question.get("options") == ["闯关", "生存"]
        assert run is not None and run.status == RunStatus.PAUSED.value

        # 用户回答 → revise 通道恢复（答案 = modify_text）
        granted = {**st, "resume_grant": {"decision": "modify", "modify_text": "生存玩法"}}
        await ckpt.save_state(redis_client, rid, granted, s)
        await s.commit()

    from app.forge.graph import run_generation

    await run_generation(ctx, rid, resume=True, decision="modify")
    assert asked["n"] == 1  # 恢复后未再提问（fake 已切回设计稿分支）

    async with db_module.SessionLocal() as s:
        st2 = await ckpt.load_state(redis_client, rid, s) or {}
        # 回答回流后离开 agent_question 并继续推进（revise → 确认/后续阶段）
        assert st2.get("phase") in ("plan_confirm", "art_confirm")


async def test_budget_exhausted_auto_continues(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "forge_ask_user_max_per_run", 0)
    _patch_plan_to_ask_once(monkeypatch)
    ctx = {"redis": redis_client}
    _gid, rid = await _make_game_run(verified_client)

    await execute_run(ctx, rid)  # 预算 0：不暂停，注入合成回答重跑

    async with db_module.SessionLocal() as s:
        st = await ckpt.load_state(redis_client, rid, s) or {}
        run = await s.get(GenerationRun, rid)
        assert st.get("phase") == "plan_confirm"
        assert run is not None and run.status == RunStatus.PAUSED.value  # 正常确认门暂停


async def test_enqueue_skip_uses_synthetic_answer(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """skip 决策 → revise 通道 + 合成回答（queue 归一）。"""
    from conftest import _real_enqueue_resume

    from app.forge.ask_user import synthetic_answer

    _patch_plan_to_ask_once(monkeypatch)
    ctx = {"redis": redis_client}
    _gid, rid = await _make_game_run(verified_client)
    await execute_run(ctx, rid)

    async with db_module.SessionLocal() as s:
        # conftest 为直驱 run_generation 把 enqueue_resume 换成 no-op；这里测真实入队路径
        command_id = await _real_enqueue_resume(
            s, ctx["redis"], rid, "skip", None, source="hitl"
        )
        await s.commit()
    assert command_id is not None

    async with db_module.SessionLocal() as s:
        st = await ckpt.load_state(redis_client, rid, s) or {}
        grant = st.get("resume_grant") or {}
        assert grant.get("decision") == "modify"
        assert grant.get("modify_text") == synthetic_answer()
