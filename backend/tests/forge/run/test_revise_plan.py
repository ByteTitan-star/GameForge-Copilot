"""P2：REVISE_PLAN 合同、跨阶段路由、独立 replan budget。"""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.core.config import settings
from app.core.errors import ErrorCode
from app.enums import RunCommandType
from app.forge.commands import normalize_resume_command
from app.forge.hitl import allowed_commands_for
from app.models.run_command import RunCommand


def test_qa_failed_allows_revise_plan_and_retry() -> None:
    cmds = allowed_commands_for("qa_failed")
    assert RunCommandType.RETRY_IMPLEMENTATION.value in cmds
    assert RunCommandType.REVISE_PLAN.value in cmds
    assert RunCommandType.CANCEL_RUN.value in cmds


def test_art_confirm_allows_revise_plan() -> None:
    cmds = allowed_commands_for("art_confirm")
    assert RunCommandType.REVISE_PLAN.value in cmds
    assert RunCommandType.SELECT_ART_A.value in cmds


def test_plan_confirm_allows_cancel_run() -> None:
    assert RunCommandType.CANCEL_RUN.value in allowed_commands_for("plan_confirm")


def test_normalize_command_field_overrides_legacy_decision() -> None:
    mapped = normalize_resume_command(
        phase="qa_failed",
        decision="approve",
        command=RunCommandType.REVISE_PLAN.value,
        feedback="改成 2D 单机",
    )
    assert mapped.command_type == RunCommandType.REVISE_PLAN
    assert mapped.payload.get("feedback") == "改成 2D 单机"


def test_legacy_qa_approve_still_retry_implementation() -> None:
    mapped = normalize_resume_command(phase="qa_failed", decision="approve")
    assert mapped.command_type == RunCommandType.RETRY_IMPLEMENTATION


async def _to_qa_failed(
    client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[uuid.UUID, uuid.UUID]:
    from app.forge.graph import run_generation
    from app.forge.runner import execute_run
    from app.sandbox.playtest import PlaytestResult

    async def _fail(_html: str, **_kwargs: object) -> PlaytestResult:
        return PlaytestResult(ok=False, errors=["mock"], console_logs=[], failure_kind="product")

    monkeypatch.setattr("app.forge.code_qa_exec.run_playtest", _fail)
    monkeypatch.setattr(settings, "code_qa_max_attempts", 1)

    gid = uuid.UUID(
        (
            await client.post(
                "/api/v1/games", json={"title": "Replan P2", "requirement": "测试改策划"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()["data"][
            "run_id"
        ]
    )
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)

    async def _grant(decision: str) -> None:
        async with db_module.SessionLocal() as s:
            from app.forge import state as ckpt

            st = await ckpt.load_state(redis_client, rid, s) or {}
            granted = {**st, "resume_grant": {"decision": decision, "modify_text": None}}
            await ckpt.save_state(redis_client, rid, granted, s)
            await s.commit()

    await _grant("approve")
    await run_generation(ctx, rid, resume=True, decision="approve")
    await _grant("select_a")
    await run_generation(ctx, rid, resume=True, decision="select_a")
    return gid, rid


async def test_qa_failed_revise_plan_returns_to_plan_confirm(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.forge import state as ckpt
    from app.forge.runner import resume_run

    gid, rid = await _to_qa_failed(verified_client, redis_client, monkeypatch)

    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={
            "node": "qa_failed",
            "command": "revise_plan",
            "modify_text": "改成更简单的 2D 玩法",
        },
    )
    assert r.status_code == 200, r.text

    async with db_module.SessionLocal() as s:
        row = await s.scalar(select(RunCommand).where(RunCommand.run_id == rid))
        assert row is not None
        assert row.command_type == RunCommandType.REVISE_PLAN.value
        st = await ckpt.load_state(redis_client, rid, s) or {}
        assert st.get("replan_count") == 1
        assert isinstance(st.get("superseded"), dict)
        assert "design_doc" in (st.get("superseded") or {})
        command_id = uuid.UUID(st["resume_grant"]["command_id"])

    await resume_run({"redis": redis_client}, rid, "modify", "改成更简单的 2D 玩法", command_id)
    st2 = await ckpt.load_state(redis_client, rid)
    assert st2 is not None
    assert st2.get("phase") == "plan_confirm"


async def test_replan_budget_blocks_extra_revision(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "replan_max_revisions", 1)
    gid, rid = await _to_qa_failed(verified_client, redis_client, monkeypatch)

    async with db_module.SessionLocal() as s:
        from app.forge import state as ckpt

        st = await ckpt.load_state(redis_client, rid, s) or {}
        st["replan_count"] = 1
        await ckpt.save_state(redis_client, rid, st, s)
        await s.commit()

    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "qa_failed", "command": "revise_plan", "modify_text": "再改一次"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == ErrorCode.INVALID_STATE.value


async def test_hitl_wait_payload_includes_allowed_commands(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[dict] = []
    from app.forge import graph

    real_publish = graph.publish_event

    async def _capture(run_id: object, event_type: object, payload: dict, **kwargs: object) -> None:
        from app.enums import WSEventType

        if event_type == WSEventType.HITL_WAIT:
            captured.append(payload)
        await real_publish(run_id, event_type, payload, **kwargs)

    monkeypatch.setattr(graph, "publish_event", _capture)
    await _to_qa_failed(verified_client, redis_client, monkeypatch)
    assert captured, "应至少发出一次 HITL_WAIT"
    last = captured[-1]
    assert "allowed_commands" in last
    assert RunCommandType.REVISE_PLAN.value in last["allowed_commands"]
    assert "control_revision" in last
    assert last.get("failure") is None or "failure_class" in last["failure"]


async def test_cancel_run_command_from_plan_confirm(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    from app.forge.runner import execute_run

    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "Cancel P2", "requirement": "取消"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )
    await execute_run({"redis": redis_client}, rid)

    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs/{rid}/hitl/resolve",
        json={"node": "plan_confirm", "command": "cancel_run"},
    )
    assert r.status_code == 200, r.text
    detail = await verified_client.get(f"/api/v1/runs/{rid}")
    assert detail.json()["data"]["status"] == "failed"
