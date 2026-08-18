"""P0：legacy decision → RunCommand、control_revision CAS、command 幂等。"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.errors import ErrorCode
from app.enums import PauseReason, RunCommandStatus, RunCommandType
from app.forge.commands import normalize_resume_command
from app.forge.runner import resume_run
from app.models.run_command import RunCommand


def test_plan_confirm_maps_approve_and_modify() -> None:
    assert (
        normalize_resume_command(phase="plan_confirm", decision="approve").command_type
        == RunCommandType.APPROVE_PLAN
    )
    mapped = normalize_resume_command(phase="plan_confirm", decision="modify", feedback="改成 2D")
    assert mapped.command_type == RunCommandType.REVISE_PLAN
    assert mapped.payload["feedback"] == "改成 2D"


def test_art_confirm_maps_select_and_revise() -> None:
    assert (
        normalize_resume_command(phase="art_confirm", decision="select_a").command_type
        == RunCommandType.SELECT_ART_A
    )
    assert (
        normalize_resume_command(phase="art_confirm", decision="select_b").command_type
        == RunCommandType.SELECT_ART_B
    )
    assert (
        normalize_resume_command(phase="art_confirm", decision="modify").command_type
        == RunCommandType.REVISE_ART
    )


def test_qa_and_sandbox_failed_keep_retry_implementation() -> None:
    for phase in ("qa_failed", "sandbox_failed"):
        for decision in ("approve", "modify"):
            mapped = normalize_resume_command(phase=phase, decision=decision)
            assert mapped.command_type == RunCommandType.RETRY_IMPLEMENTATION


def test_recoverable_pause_maps_retry_infra() -> None:
    mapped = normalize_resume_command(
        phase="code",
        decision="approve",
        pause_reason=PauseReason.RECOVERABLE_ERROR.value,
    )
    assert mapped.command_type == RunCommandType.RETRY_INFRA


def test_four_resume_sources_all_normalize() -> None:
    sources = ("hitl", "resume_control", "retry", "dev_requeue")
    for source in sources:
        mapped = normalize_resume_command(phase="qa_failed", decision="approve", source=source)
        assert mapped.command_type == RunCommandType.RETRY_IMPLEMENTATION
        assert mapped.source == source


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post(
        "/api/v1/games", json={"title": "Command P0", "requirement": "测试 command"}
    )
    return uuid.UUID(r.json()["data"]["game_id"])


async def _paused_plan_run(
    client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm: object,
) -> tuple[uuid.UUID, uuid.UUID]:
    from app.forge.runner import execute_run

    gid = await _make_game(client)
    rid = uuid.UUID(
        (await client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()["data"][
            "run_id"
        ]
    )
    await execute_run({"redis": redis_client}, rid)
    return gid, rid


async def test_hitl_resolve_writes_run_command(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid, rid = await _paused_plan_run(verified_client, redis_client, _fake_llm)
    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "plan_confirm", "decision": "approve"},
    )
    assert r.status_code == 200, r.text
    async with db_module.SessionLocal() as s:
        row = await s.scalar(select(RunCommand).where(RunCommand.run_id == rid))
        assert row is not None
        assert row.command_type == RunCommandType.APPROVE_PLAN.value
        assert row.status == RunCommandStatus.PENDING.value


async def test_stale_control_revision_returns_409(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid, rid = await _paused_plan_run(verified_client, redis_client, _fake_llm)
    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={
            "node": "plan_confirm",
            "decision": "approve",
            "expected_control_revision": 999,
        },
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == ErrorCode.STALE_DECISION.value


async def test_double_resolve_second_call_is_stale(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    gid, rid = await _paused_plan_run(verified_client, redis_client, _fake_llm)
    body = {
        "node": "plan_confirm",
        "decision": "approve",
        "expected_control_revision": 0,
    }
    first = await verified_client.post(f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve", json=body)
    assert first.status_code == 200, first.text
    second = await verified_client.post(f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve", json=body)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_succeeded_command_is_not_executed_again(monkeypatch: pytest.MonkeyPatch) -> None:
    gen = AsyncMock()
    monkeypatch.setattr("app.forge.runner.run_generation", gen)
    monkeypatch.setattr(
        "app.forge.runner.command_already_succeeded",
        AsyncMock(return_value=True),
    )
    await resume_run(
        {"redis": None},
        uuid.uuid4(),
        "approve",
        None,
        command_id=uuid.uuid4(),
    )
    gen.assert_not_awaited()


async def test_hitl_pause_marks_command_succeeded_before_worker_ack(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """业务 HITL commit 必须带上 SUCCEEDED，不能等 runner 在 ACK 前补标。"""
    gid, rid = await _paused_plan_run(verified_client, redis_client, _fake_llm)
    posted = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "plan_confirm", "decision": "approve"},
    )
    assert posted.status_code == 200, posted.text
    async with db_module.SessionLocal() as s:
        row = await s.scalar(select(RunCommand).where(RunCommand.run_id == rid))
        assert row is not None
        assert row.status == RunCommandStatus.PENDING.value
        command_id = row.id

    monkeypatch.setattr("app.forge.runner.mark_command_succeeded", AsyncMock())
    await resume_run({"redis": redis_client}, rid, "approve", None, command_id=command_id)

    async with db_module.SessionLocal() as s:
        row = await s.get(RunCommand, command_id)
        assert row is not None
        assert row.status == RunCommandStatus.SUCCEEDED.value
        assert row.completed_at is not None
