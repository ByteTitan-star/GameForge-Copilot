"""P3 Artifact lineage：Revision 只增不删；Promote 前校验 ACTIVE + 依赖一致。"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.metrics import ART_REGENERATE, ART_REUSE
from app.enums import ArtifactKind, ArtifactStatus
from app.forge.art_fingerprint import art_dependency_fingerprint, can_reuse_art
from app.models.artifact_revision import ArtifactRevision

STALE_PLAN_SUPERSEDED = "PLAN_SUPERSEDED"


def check_promotion_guard(
    *,
    status: str | None,
    plan_revision_id: str | None,
    art_revision_id: str | None,
    active_plan_revision_id: str | None,
    active_art_revision_id: str | None,
) -> None:
    if status is None and plan_revision_id is None:
        return
    if status != ArtifactStatus.ACTIVE.value:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物已过期，不能发布")
    if plan_revision_id and active_plan_revision_id and plan_revision_id != active_plan_revision_id:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物与当前策划不一致")
    if art_revision_id and active_art_revision_id and art_revision_id != active_art_revision_id:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物与当前美术不一致")


def payload_hash(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def _active_of_kind(
    db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind
) -> ArtifactRevision | None:
    return await db.scalar(
        select(ArtifactRevision).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == kind.value,
            ArtifactRevision.status == ArtifactStatus.ACTIVE.value,
        )
    )


async def _next_revision(db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind) -> int:
    current = await db.scalar(
        select(func.max(ArtifactRevision.revision)).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == kind.value,
        )
    )
    return int(current or 0) + 1


async def _stale_kind(db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind, reason: str) -> None:
    rows = list(
        (
            await db.scalars(
                select(ArtifactRevision).where(
                    ArtifactRevision.run_id == run_id,
                    ArtifactRevision.kind == kind.value,
                    ArtifactRevision.status == ArtifactStatus.ACTIVE.value,
                )
            )
        ).all()
    )
    for row in rows:
        row.status = ArtifactStatus.STALE.value
        row.stale_reason = reason


async def stale_downstream(db: AsyncSession, run_id: uuid.UUID) -> None:
    await _stale_kind(db, run_id, ArtifactKind.ART, STALE_PLAN_SUPERSEDED)
    await _stale_kind(db, run_id, ArtifactKind.CANDIDATE, STALE_PLAN_SUPERSEDED)


async def ensure_plan_revision(
    db: AsyncSession,
    run_id: uuid.UUID,
    design_doc: dict[str, Any],
    *,
    force_new: bool = False,
) -> tuple[ArtifactRevision, bool, bool]:
    digest = payload_hash(design_doc)
    current = await _active_of_kind(db, run_id, ArtifactKind.PLAN)
    if current is not None and not force_new and payload_hash(current.payload) == digest:
        return current, False, False
    superseded = current.id if current is not None else None
    art_reused = False
    if current is not None:
        current.status = ArtifactStatus.STALE.value
        current.stale_reason = STALE_PLAN_SUPERSEDED
        art_reused = await _reuse_or_stale_art(db, run_id, design_doc)
    row = ArtifactRevision(
        run_id=run_id,
        kind=ArtifactKind.PLAN.value,
        revision=await _next_revision(db, run_id, ArtifactKind.PLAN),
        status=ArtifactStatus.ACTIVE.value,
        supersedes=superseded,
        payload=design_doc,
    )
    db.add(row)
    await db.flush()
    return row, True, art_reused


async def _reuse_or_stale_art(
    db: AsyncSession, run_id: uuid.UUID, design_doc: dict[str, Any]
) -> bool:
    art = await _active_of_kind(db, run_id, ArtifactKind.ART)
    new_fp, new_ver = art_dependency_fingerprint(design_doc)
    reusable = art is not None and can_reuse_art(
        stored_fp=art.dependency_fingerprint,
        stored_version=art.fingerprint_version,
        new_fp=new_fp,
        new_version=new_ver,
    )
    if reusable:
        await _stale_kind(db, run_id, ArtifactKind.CANDIDATE, STALE_PLAN_SUPERSEDED)
        ART_REUSE.inc()
        return True
    await stale_downstream(db, run_id)
    ART_REGENERATE.inc()
    return False


async def ensure_art_revision(
    db: AsyncSession,
    run_id: uuid.UUID,
    art_direction: dict[str, Any],
    *,
    plan_revision_id: uuid.UUID | None,
    design_doc: dict[str, Any] | None = None,
) -> ArtifactRevision:
    current = await _active_of_kind(db, run_id, ArtifactKind.ART)
    if current is not None and payload_hash(current.payload) == payload_hash(art_direction):
        return current
    await _stale_kind(db, run_id, ArtifactKind.ART, STALE_PLAN_SUPERSEDED)
    digest, version = art_dependency_fingerprint(design_doc)
    row = ArtifactRevision(
        run_id=run_id,
        kind=ArtifactKind.ART.value,
        revision=await _next_revision(db, run_id, ArtifactKind.ART),
        status=ArtifactStatus.ACTIVE.value,
        supersedes=current.id if current is not None else None,
        plan_revision_id=plan_revision_id,
        dependency_fingerprint=digest,
        fingerprint_version=version,
        payload=art_direction,
    )
    db.add(row)
    await db.flush()
    return row


async def record_candidate_revision(
    db: AsyncSession,
    run_id: uuid.UUID,
    *,
    version: int,
    plan_revision_id: uuid.UUID | None,
    art_revision_id: uuid.UUID | None,
) -> ArtifactRevision:
    existing = await db.scalar(
        select(ArtifactRevision).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == ArtifactKind.CANDIDATE.value,
            ArtifactRevision.candidate_version == version,
        )
    )
    if existing is not None:
        return existing
    row = ArtifactRevision(
        run_id=run_id,
        kind=ArtifactKind.CANDIDATE.value,
        revision=await _next_revision(db, run_id, ArtifactKind.CANDIDATE),
        status=ArtifactStatus.ACTIVE.value,
        plan_revision_id=plan_revision_id,
        art_revision_id=art_revision_id,
        candidate_version=version,
        payload={"version": version},
    )
    db.add(row)
    await db.flush()
    return row


async def assert_candidate_promotable(
    db: AsyncSession,
    run_id: uuid.UUID,
    version: int,
    checkpoint: dict[str, Any],
) -> None:
    row = await db.scalar(
        select(ArtifactRevision).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == ArtifactKind.CANDIDATE.value,
            ArtifactRevision.candidate_version == version,
        )
    )
    if row is None:
        if _id(checkpoint.get("active_plan_revision_id")) or _id(
            checkpoint.get("active_art_revision_id")
        ):
            raise AppError(
                ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT,
                "候选产物缺少版本记录，不能发布",
            )
        return
    check_promotion_guard(
        status=row.status,
        plan_revision_id=str(row.plan_revision_id) if row.plan_revision_id else None,
        art_revision_id=str(row.art_revision_id) if row.art_revision_id else None,
        active_plan_revision_id=_id(checkpoint.get("active_plan_revision_id")),
        active_art_revision_id=_id(checkpoint.get("active_art_revision_id")),
    )


async def persist_candidate_revision(
    db: AsyncSession,
    redis: Any,
    run_id: uuid.UUID,
    version: int,
) -> ArtifactRevision:
    from app.forge import state as ckpt

    st = await ckpt.load_state(redis, run_id, db) or {}
    row = await record_candidate_revision(
        db,
        run_id,
        version=version,
        plan_revision_id=parse_revision_id(st.get("active_plan_revision_id")),
        art_revision_id=parse_revision_id(st.get("active_art_revision_id")),
    )
    st["active_candidate_revision_id"] = str(row.id)
    await ckpt.save_state(redis, run_id, st, db)
    return row


def _id(raw: object) -> str | None:
    text = str(raw or "").strip()
    return text or None


def parse_revision_id(raw: object) -> uuid.UUID | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None
