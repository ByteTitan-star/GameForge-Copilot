"""P1：FailureReport Lite — 确定性分类、脱敏、HITL 前冻结。"""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.enums import FailureClass
from app.forge.failure import classify_failure, persist_failure_report, sanitize_failure_text
from app.models.failure_report import FailureReport


def test_http_503_is_infra_not_capability() -> None:
    result = classify_failure(errors=["sandbox control plane HTTP 503"])
    assert result.failure_class == FailureClass.INFRA_TRANSIENT
    assert result.failure_class != FailureClass.CAPABILITY_MISMATCH
    assert result.classification_source == "DETERMINISTIC_RULE"


def test_playwright_missing_is_infra() -> None:
    result = classify_failure(
        errors=["PLAYWRIGHT_UNAVAILABLE: playwright package is not installed"],
        failure_kind="infra",
    )
    assert result.failure_class == FailureClass.INFRA_TRANSIENT


def test_pageerror_is_implementation() -> None:
    result = classify_failure(
        errors=["PAGE_ERROR: Foo is not defined"],
        failure_kind="product",
    )
    assert result.failure_class == FailureClass.IMPLEMENTATION_DEFECT


def test_empty_evidence_is_unknown() -> None:
    result = classify_failure(errors=[])
    assert result.failure_class == FailureClass.UNKNOWN


def test_provider_5xx_code_is_infra() -> None:
    result = classify_failure(error_code="provider_5xx")
    assert result.failure_class == FailureClass.INFRA_TRANSIENT


def test_sandbox_oom_is_resource_exceeded() -> None:
    result = classify_failure(error_code="sandbox_oom")
    assert result.failure_class == FailureClass.RESOURCE_EXCEEDED


def test_weak_worker_interrupted_stays_unknown() -> None:
    result = classify_failure(error_code="worker_interrupted", errors=["net boom"])
    assert result.failure_class == FailureClass.UNKNOWN


def test_sanitize_truncates_and_redacts_secrets() -> None:
    blob = "Authorization: Bearer super-secret-token-value " + ("x" * 4000)
    cleaned = sanitize_failure_text(blob)
    assert "super-secret-token-value" not in cleaned
    assert "Bearer" not in cleaned or "[REDACTED]" in cleaned
    assert len(cleaned) <= 500


async def test_qa_exhausted_persists_report_before_hitl(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import settings
    from app.forge.graph import run_generation
    from app.forge.runner import execute_run
    from app.sandbox.playtest import PlaytestResult

    async def _fail(_html: str, **_kwargs: object) -> PlaytestResult:
        return PlaytestResult(
            ok=False, errors=["PAGE_ERROR: mock"], console_logs=[], failure_kind="product"
        )

    monkeypatch.setattr("app.forge.code_qa_exec.run_playtest", _fail)
    monkeypatch.setattr(settings, "code_qa_max_attempts", 1)

    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "Failure P1", "requirement": "测试失败报告"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )
    ctx = {"redis": redis_client}
    await execute_run(ctx, rid)

    async with db_module.SessionLocal() as s:
        from app.forge import state as ckpt

        st = await ckpt.load_state(redis_client, rid, s) or {}
        granted = {**st, "resume_grant": {"decision": "approve", "modify_text": None}}
        await ckpt.save_state(redis_client, rid, granted, s)
        await s.commit()
    await run_generation(ctx, rid, resume=True, decision="approve")
    async with db_module.SessionLocal() as s:
        from app.forge import state as ckpt

        st = await ckpt.load_state(redis_client, rid, s) or {}
        granted = {**st, "resume_grant": {"decision": "select_a", "modify_text": None}}
        await ckpt.save_state(redis_client, rid, granted, s)
        await s.commit()
    await run_generation(ctx, rid, resume=True, decision="select_a")

    async with db_module.SessionLocal() as s:
        rows = list(
            (await s.scalars(select(FailureReport).where(FailureReport.run_id == rid))).all()
        )
        assert len(rows) == 1
        report = rows[0]
        assert report.failure_class == FailureClass.IMPLEMENTATION_DEFECT.value
        first_id = report.id
        diagnosis = report.diagnosis if isinstance(report.diagnosis, dict) else {}
        first_summary = diagnosis.get("summary")
        from app.forge import state as ckpt

        st = await ckpt.load_state(redis_client, rid, s) or {}
        assert st.get("failure_report_id") == str(first_id)
        st["playtest_errors"] = ["later checkpoint mutation must not rewrite F1"]
        await ckpt.save_state(redis_client, rid, st, s)
        await persist_failure_report(
            s, run_id=rid, errors=["second failure F2"], failure_kind="product"
        )
        await s.commit()

        again = await s.get(FailureReport, first_id)
        assert again is not None
        again_diagnosis = again.diagnosis if isinstance(again.diagnosis, dict) else {}
        again_summary = again_diagnosis.get("summary")
        assert again_summary == first_summary
        assert "later checkpoint mutation" not in str(again.evidence)
        all_rows = list(
            (await s.scalars(select(FailureReport).where(FailureReport.run_id == rid))).all()
        )
        assert len(all_rows) == 2


async def test_recoverable_pause_persists_report(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.forge import graph

    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "Recover P1", "requirement": "暂停落库"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )

    async def _boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("net boom")

    async def _noop_event(*_a: object, **_k: object) -> None:
        return None

    monkeypatch.setattr(graph, "_run_body", _boom)
    monkeypatch.setattr(graph, "publish_event", _noop_event)
    await graph.run_generation({"redis": redis_client}, rid)

    async with db_module.SessionLocal() as s:
        rows = list(
            (await s.scalars(select(FailureReport).where(FailureReport.run_id == rid))).all()
        )
        assert len(rows) == 1
        assert rows[0].failure_class == FailureClass.UNKNOWN.value
