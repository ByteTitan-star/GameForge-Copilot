"""流式 + 护栏集成测试：正常路径发 LLM_DELTA/LLM_CALL/DONE；审核命中发 ATTACKED + run FAILED。

通过 monkeypatch guard.build_guard 控制命中/不命中；通过 list_events 断言 WS 事件序列。
"""

import json
import uuid

import fakeredis.aioredis
import httpx
import pytest

from app.enums import RunStatus, WSEventType
from app.forge import guard
from app.forge.event_log import list_events
from app.forge.runner import execute_run


def _parse_events(raw_events: list[str]) -> list[dict]:
    return [json.loads(line) for line in raw_events]


def _event_types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


async def _make_plan_run(verified_client: httpx.AsyncClient) -> tuple[uuid.UUID, uuid.UUID]:
    """创建 game + run，返回 (game_id, run_id)。plan 节点会走流式。"""
    r = await verified_client.post(
        "/api/v1/games", json={"title": "流式测试", "requirement": "做一个贪吃蛇"}
    )
    gid = uuid.UUID(r.json()["data"]["game_id"])
    run = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json={"requirement": "做一个贪吃蛇"}
    )
    return gid, uuid.UUID(run.json()["data"]["run_id"])


@pytest.mark.asyncio
async def test_normal_run_emits_llm_delta_then_call(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """正常路径：plan 阶段发若干 LLM_DELTA（打字机）+ LLM_CALL + HITL_WAIT（plan_confirm）。"""
    # 审核关闭，确保不误触（quick_filter 对正常设计稿 JSON 不命中，但显式 noop 更稳）
    orig = guard.build_guard

    async def _noop_guard(ctx=None):
        return guard.NoopGuard()

    guard.build_guard = _noop_guard
    try:
        gid, rid = await _make_plan_run(verified_client)
        await execute_run({"redis": redis_client}, rid)
    finally:
        guard.build_guard = orig

    events = _parse_events(await list_events(redis_client, rid))
    types = _event_types(events)
    assert WSEventType.LLM_DELTA in types, f"缺少 LLM_DELTA 事件，实际: {types}"
    assert WSEventType.LLM_CALL in types, f"缺少 LLM_CALL 事件，实际: {types}"
    # plan 节点结束后停在 plan_confirm HITL
    assert WSEventType.HITL_WAIT in types


@pytest.mark.asyncio
async def test_output_audit_hit_emits_attacked_and_fails_run(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch,
) -> None:
    """输出审核命中：发 ATTACKED + ERROR(CONTENT_BLOCKED)，run 置 FAILED，无后续 HITL/BUILD。"""
    from app.core.config import settings

    # mock 流瞬间完成，时间窗审核不会触发；强制每个 chunk 都触发输出审核
    monkeypatch.setattr(settings, "audit_interval_ms", 0)
    monkeypatch.setattr(settings, "audit_min_chars_between", 0)

    class _HitGuard(guard.NoopGuard):
        async def audit(self, text: str):
            # 输入侧（包了 USER_INPUT 标记的用户需求）放行；输出侧（设计稿 JSON）判恶意
            if "USER_INPUT" in text:
                return None
            return guard.AuditResult(True, category="harmful_code", reason="test", evidence="x")

    async def _hit_guard(ctx=None):
        return _HitGuard()

    monkeypatch.setattr(guard, "build_guard", _hit_guard)
    gid, rid = await _make_plan_run(verified_client)
    await execute_run({"redis": redis_client}, rid)

    events = _parse_events(await list_events(redis_client, rid))
    types = _event_types(events)
    assert WSEventType.ATTACKED in types, f"缺少 ATTACKED 事件，实际: {types}"
    # ERROR 事件 code 必须是 CONTENT_BLOCKED
    error_events = [e for e in events if e["type"] == WSEventType.ERROR]
    assert error_events and error_events[-1]["payload"]["code"] == "CONTENT_BLOCKED"
    # 命中后不应再推进到 plan_confirm HITL 或后续
    assert WSEventType.HITL_WAIT not in types

    # run 终态 FAILED
    from app.core import db as db_module
    from app.models.generation_run import GenerationRun

    async with db_module.SessionLocal() as s:
        run = await s.get(GenerationRun, rid)
        assert run.status == RunStatus.FAILED.value


@pytest.mark.asyncio
async def test_input_audit_hit_emits_attacked(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch,
) -> None:
    """输入审核命中（异步并行）：中断生成、发 ATTACKED + CONTENT_BLOCKED，run FAILED。

    输入审核与生成流并行，设计上允许部分 LLM_DELTA 先流出（输出侧同语义）；
    但 LLM_CALL 仅在流正常走完后发，命中即中断时不应出现。
    """

    class _InputHitGuard(guard.NoopGuard):
        async def audit(self, text: str):
            return guard.AuditResult(True, category="jailbreak", reason="test input", evidence="x")

    async def _input_hit_guard(ctx=None):
        return _InputHitGuard()

    monkeypatch.setattr(guard, "build_guard", _input_hit_guard)
    gid, rid = await _make_plan_run(verified_client)
    await execute_run({"redis": redis_client}, rid)

    events = _parse_events(await list_events(redis_client, rid))
    types = _event_types(events)
    assert WSEventType.ATTACKED in types
    error_events = [e for e in events if e["type"] == WSEventType.ERROR]
    assert error_events and error_events[-1]["payload"]["code"] == "CONTENT_BLOCKED"
    # 命中即中断：流未正常走完，不发 LLM_CALL，也不进 HITL
    assert WSEventType.LLM_CALL not in types
    assert WSEventType.HITL_WAIT not in types

    from app.core import db as db_module
    from app.models.generation_run import GenerationRun

    async with db_module.SessionLocal() as s:
        run = await s.get(GenerationRun, rid)
        assert run.status == RunStatus.FAILED.value
