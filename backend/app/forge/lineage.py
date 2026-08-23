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
    """Promote 前校验候选产物仍为 ACTIVE 且与当前 plan/art revision 一致。

    场景：``assert_candidate_promotable``、版本提升前门禁。
    参数：status 与各 revision_id（候选 vs 当前 active）。
    返回：无；不一致时抛 PROMOTION_REJECTED_STALE_ARTIFACT。
    """
    if status is None and plan_revision_id is None:
        return
    if status != ArtifactStatus.ACTIVE.value:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物已过期，不能发布")
    if plan_revision_id and active_plan_revision_id and plan_revision_id != active_plan_revision_id:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物与当前策划不一致")
    if art_revision_id and active_art_revision_id and art_revision_id != active_art_revision_id:
        raise AppError(ErrorCode.PROMOTION_REJECTED_STALE_ARTIFACT, "候选产物与当前美术不一致")


def payload_hash(payload: dict[str, Any]) -> str:
    """对产物 payload 做确定性 SHA256 哈希。

    场景：判断 plan/art revision 内容是否变化。
    参数：payload - 可 JSON 序列化的 dict。
    返回：hex 摘要字符串。
    """
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def _active_of_kind(
    db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind
) -> ArtifactRevision | None:
    """查询某 run 指定 kind 的 ACTIVE revision。

    场景：ensure_plan_revision / ensure_art_revision 去重判断。
    参数：db - 会话；run_id - Run ID；kind - PLAN/ART/CANDIDATE。
    返回：ArtifactRevision 或 None。
    """
    return await db.scalar(
        select(ArtifactRevision).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == kind.value,
            ArtifactRevision.status == ArtifactStatus.ACTIVE.value,
        )
    )


async def _next_revision(db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind) -> int:
    """计算某 run+kind 的下一条 revision 序号（单调递增）。

    场景：新建 ArtifactRevision 行时。
    参数：db、run_id、kind。
    返回：下一个 revision 整数。
    """
    current = await db.scalar(
        select(func.max(ArtifactRevision.revision)).where(
            ArtifactRevision.run_id == run_id,
            ArtifactRevision.kind == kind.value,
        )
    )
    return int(current or 0) + 1


async def _stale_kind(db: AsyncSession, run_id: uuid.UUID, kind: ArtifactKind, reason: str) -> None:
    """将某 kind 下所有 ACTIVE revision 标记为 STALE。

    场景：策划稿变更后作废下游 art/candidate。
    参数：db、run_id、kind、stale_reason 文案。
    返回：无（原地更新 ORM 行）。
    """
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
    """策划变更后作废 ART 与 CANDIDATE 的 ACTIVE revision。

    场景：plan revision 内容变化且 art 不可复用时。
    参数：db、run_id。
    返回：无。
    """
    await _stale_kind(db, run_id, ArtifactKind.ART, STALE_PLAN_SUPERSEDED)
    await _stale_kind(db, run_id, ArtifactKind.CANDIDATE, STALE_PLAN_SUPERSEDED)


async def ensure_plan_revision(
    db: AsyncSession,
    run_id: uuid.UUID,
    design_doc: dict[str, Any],
    *,
    force_new: bool = False,
) -> tuple[ArtifactRevision, bool, bool]:
    """确保存在与 design_doc 匹配的 ACTIVE plan revision。

    场景：plan_node / revise_plan_node 确认策划稿后。
    参数：db、run_id、design_doc、force_new - 是否强制新建 revision。
    返回：(revision 行, 是否新建, art 是否复用未重生成)。
    """
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
    """策划变更后判断现有 art revision 是否可复用。

    场景：ensure_plan_revision 在 supersede 旧 plan 时。
    参数：db、run_id、新 design_doc。
    返回：True 表示 art 可复用（仅 stale candidate）；False 表示 art 也需重做。
    """
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
    """确保存在与 art_direction 匹配的 ACTIVE art revision。

    场景：art_detail_node 生成美术实现设计后。
    参数：db、run_id、art_direction、plan_revision_id、design_doc（算指纹）。
    返回：ACTIVE 的 ArtifactRevision。
    """
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
    """记录或返回已存在的 CANDIDATE revision（幂等按 version）。

    场景：Code 阶段 commit candidate 后登记谱系。
    参数：db、run_id、version、plan/art revision 外键。
    返回：CANDIDATE ArtifactRevision。
    """
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
    """Promote 前断言候选版本 revision 链路与 checkpoint 一致。

    场景：code_qa_loop promote_candidate 之前。
    参数：db、run_id、候选 version、checkpoint 中的 active_*_revision_id。
    返回：无；不可 promote 时抛 AppError。
    """
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
    """写入 candidate revision 并更新 checkpoint 的 active_candidate_revision_id。

    场景：QA 通过后 promote 流程。
    参数：db、redis、run_id、game_version 号。
    返回：新或已有的 CANDIDATE ArtifactRevision。
    """
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
    """把 checkpoint 中的 revision id 规范为非空字符串或 None。

    场景：check_promotion_guard / assert_candidate_promotable。
    参数：raw - 任意对象。
    返回：strip 后的字符串或 None。
    """
    text = str(raw or "").strip()
    return text or None


def parse_revision_id(raw: object) -> uuid.UUID | None:
    """从 checkpoint 字符串解析 UUID revision id。

    场景：persist_candidate_revision 读取 active_plan/art revision。
    参数：raw - 字符串或 None。
    返回：uuid.UUID 或 None（非法格式）。
    """
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return uuid.UUID(text)
    except ValueError:
        return None
