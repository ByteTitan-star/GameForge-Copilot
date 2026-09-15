"""ask_user 端到端（ADR-18 原生工具）：plan 提问暂停 → 回答恢复；预算耗尽不绑工具。"""

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

_ASK_ARGS = {
    "reason": "题材方向决定玩法形态",
    "question": "想要闯关还是生存？",
    "options": ["闯关", "生存"],
}


def _ask_tool_completion() -> LLMCompletion:
    return LLMCompletion(
        content="",
        usage=Usage(5, 2),
        finish_reason="tool_calls",
        tool_calls=[
            {
                "id": "call_ask_1",
                "type": "function",
                "function": {
                    "name": "ask_user",
                    "arguments": json.dumps(_ASK_ARGS, ensure_ascii=False),
                },
            }
        ],
    )


def _patch_plan_to_ask_once(monkeypatch: pytest.MonkeyPatch) -> dict:
    """首次「绑定了工具」的调用返回 ask_user 工具调用，其余委托 _fake_llm。

    原生协议：工具调用只在请求绑定 tools 时可能发生（tool_calls 字段返回）。
    """
    base_call = llm_client.call_llm
    base_stream = llm_client.call_llm_stream
    asked = {"n": 0}

    def _hit(kw: dict) -> LLMCompletion | None:
        if kw.get("tools") and asked["n"] == 0:
            asked["n"] += 1
            return _ask_tool_completion()
        return None

    async def _call(db, r, user_id, config_id, system, user_msg, **kw):
        hit = _hit(kw)
        if hit is not None:
            return hit, LLMProvider.ANTHROPIC
        return await base_call(db, r, user_id, config_id, system, user_msg, **kw)

    async def _stream(db, r, user_id, config_id, system, user_msg, **kw):
        hit = _hit(kw)
        if hit is not None:
            # 纯工具调用：无正文增量，末帧聚合 tool_calls
            yield StreamChunk(delta="", usage=hit.usage, tool_calls=hit.tool_calls)
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
        assert st.get("ask_node") == "plan"
        question = st.get("agent_question") or {}
        assert question.get("question") == "想要闯关还是生存？"
        assert question.get("options") == ["闯关", "生存"]
        assert run is not None and run.status == RunStatus.PAUSED.value

        # 用户回答 → answer_question 通道恢复（答案 = modify_text，原生工具回填）
        granted = {
            **st,
            "resume_grant": {
                "decision": "modify",
                "modify_text": "生存玩法",
                "command_type": "answer_question",
            },
        }
        await ckpt.save_state(redis_client, rid, granted, s)
        await s.commit()

    from app.forge.graph import run_generation

    await run_generation(ctx, rid, resume=True, decision="modify")
    assert asked["n"] == 1  # 恢复后未再提问（预算内二次绑定但 fake 已切回设计稿分支）

    async with db_module.SessionLocal() as s:
        st2 = await ckpt.load_state(redis_client, rid, s) or {}
        run2 = await s.get(GenerationRun, rid)
        # ADR-18：无确认门——回答注入后整条流水线连续跑通至 done
        assert run2 is not None and run2.status == RunStatus.DONE.value
        assert st2 in (None, {}) or st2.get("phase") != "agent_question"


async def test_budget_exhausted_never_binds_tools(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """预算 0：请求根本不绑定工具——模型无法发起 ask_user，run 直接跑通。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "forge_ask_user_max_per_run", 0)
    asked = _patch_plan_to_ask_once(monkeypatch)
    ctx = {"redis": redis_client}
    _gid, rid = await _make_game_run(verified_client)

    await execute_run(ctx, rid)

    assert asked["n"] == 0  # tools 从未绑定 → 伪 tool_calls 未触发
    async with db_module.SessionLocal() as s:
        run = await s.get(GenerationRun, rid)
        assert run is not None and run.status == RunStatus.DONE.value


async def test_enqueue_skip_uses_synthetic_answer(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """skip 决策 → answer_question 命令 + 合成回答（queue 归一）。"""
    from conftest import _real_enqueue_resume

    from app.forge.tools import synthetic_answer

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
        assert grant.get("command_type") == "answer_question"
