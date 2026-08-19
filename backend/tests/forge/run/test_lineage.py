"""P3：Artifact lineage — STALE Candidate 不可 Promote，Replan 不删旧行。"""

from __future__ import annotations

import uuid

import fakeredis.aioredis
import httpx
import pytest
from sqlalchemy import func, select

from app.core import db as db_module
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import ArtifactKind, ArtifactStatus
from app.forge.lineage import assert_candidate_promotable, check_promotion_guard
from app.models.artifact_revision import ArtifactRevision
from app.models.game_version import GameVersion


def test_stale_candidate_cannot_promote() -> None:
    with pytest.raises(AppError) as exc:
        check_promotion_guard(
            status=ArtifactStatus.STALE.value,
            plan_revision_id="plan-1",
            art_revision_id="art-1",
            active_plan_revision_id="plan-1",
            active_art_revision_id="art-1",
        )
    assert exc.value.code == ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT


def test_plan_mismatch_cannot_promote() -> None:
    with pytest.raises(AppError) as exc:
        check_promotion_guard(
            status=ArtifactStatus.ACTIVE.value,
            plan_revision_id="plan-1",
            art_revision_id="art-1",
            active_plan_revision_id="plan-2",
            active_art_revision_id="art-1",
        )
    assert exc.value.code == ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT


def test_matching_active_candidate_is_promotable() -> None:
    check_promotion_guard(
        status=ArtifactStatus.ACTIVE.value,
        plan_revision_id="plan-1",
        art_revision_id="art-1",
        active_plan_revision_id="plan-1",
        active_art_revision_id="art-1",
    )


def test_legacy_missing_candidate_is_skipped() -> None:
    check_promotion_guard(
        status=None,
        plan_revision_id=None,
        art_revision_id=None,
        active_plan_revision_id=None,
        active_art_revision_id=None,
    )


async def test_missing_lineage_row_rejected_when_plan_pointer_exists() -> None:
    async with db_module.SessionLocal() as s:
        with pytest.raises(AppError) as exc:
            await assert_candidate_promotable(
                s,
                uuid.uuid4(),
                1,
                {"active_plan_revision_id": str(uuid.uuid4())},
            )
    assert exc.value.code == ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT


async def test_missing_lineage_row_allowed_for_legacy_checkpoint() -> None:
    async with db_module.SessionLocal() as s:
        await assert_candidate_promotable(s, uuid.uuid4(), 1, {})


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
                "/api/v1/games", json={"title": "Lineage P3", "requirement": "测试 lineage"}
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


async def test_replan_keeps_old_plan_and_stales_candidate(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.forge import state as ckpt
    from app.forge.runner import resume_run

    gid, rid = await _to_qa_failed(verified_client, redis_client, monkeypatch)

    async with db_module.SessionLocal() as s:
        versions_before = int(await s.scalar(select(func.count()).select_from(GameVersion)) or 0)
        plans = list(
            (
                await s.scalars(
                    select(ArtifactRevision).where(
                        ArtifactRevision.run_id == rid,
                        ArtifactRevision.kind == ArtifactKind.PLAN.value,
                    )
                )
            ).all()
        )
        candidates = list(
            (
                await s.scalars(
                    select(ArtifactRevision).where(
                        ArtifactRevision.run_id == rid,
                        ArtifactRevision.kind == ArtifactKind.CANDIDATE.value,
                    )
                )
            ).all()
        )
        arts = list(
            (
                await s.scalars(
                    select(ArtifactRevision).where(
                        ArtifactRevision.run_id == rid,
                        ArtifactRevision.kind == ArtifactKind.ART.value,
                    )
                )
            ).all()
        )
        assert plans, "qa_failed 前应已有 Plan revision"
        assert candidates, "qa_failed 前应已有 Candidate revision"
        assert arts, "qa_failed 前应已有 Art revision"
        old_plan_id = plans[0].id
        old_candidate = candidates[0]
        old_art_id = arts[0].id
        old_version = int(old_candidate.candidate_version or 0)

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
        st = await ckpt.load_state(redis_client, rid, s) or {}
        command_id = uuid.UUID(st["resume_grant"]["command_id"])

    await resume_run({"redis": redis_client}, rid, "modify", "改成更简单的 2D 玩法", command_id)

    async with db_module.SessionLocal() as s:
        st = await ckpt.load_state(redis_client, rid, s) or {}
        versions_after = int(await s.scalar(select(func.count()).select_from(GameVersion)) or 0)
        old_plan = await s.get(ArtifactRevision, old_plan_id)
        old_cand = await s.get(ArtifactRevision, old_candidate.id)
        old_art = await s.get(ArtifactRevision, old_art_id)
        active_plans = list(
            (
                await s.scalars(
                    select(ArtifactRevision).where(
                        ArtifactRevision.run_id == rid,
                        ArtifactRevision.kind == ArtifactKind.PLAN.value,
                        ArtifactRevision.status == ArtifactStatus.ACTIVE.value,
                    )
                )
            ).all()
        )
        assert old_plan is not None
        assert old_cand is not None
        assert old_plan.status == ArtifactStatus.STALE.value
        assert old_cand.status == ArtifactStatus.STALE.value
        assert old_cand.stale_reason == "PLAN_SUPERSEDED"
        assert old_art is not None
        assert old_art.status == ArtifactStatus.ACTIVE.value
        assert len(active_plans) == 1
        assert active_plans[0].id != old_plan_id
        assert versions_after >= versions_before
        assert st.get("active_art_revision_id") == str(old_art_id)
        assert st.get("active_candidate_revision_id") in (None, "")
        with pytest.raises(AppError) as exc:
            await assert_candidate_promotable(s, rid, old_version, st)
        assert exc.value.code == ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT
