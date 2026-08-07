"""发布审批工作流：submit / queue / approve / reject / take_down + 审计。

状态机见 docs/04。admin 操作（approve/reject/take_down）落 audit_logs。
slug 在 approve 时分配（全局唯一）。审批/下架发通知邮件。
"""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, PublishStatus
from app.games import services as game_services
from app.models.audit_log import AuditLog
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.publish_request import PublishRequest
from app.models.user import User
from app.notify import services as notify_services

_SUBMITTABLE = {GameStatus.DRAFT, GameStatus.REJECTED, GameStatus.TAKEN_DOWN}
_REVIEWABLE = {PublishStatus.SUBMITTED, PublishStatus.REVIEWING}


def _gen_slug(title: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    if not base:
        base = "game"
    return f"{base}-{uuid.uuid4().hex[:8]}"


async def _audit(
    db: AsyncSession, actor_id: uuid.UUID, action: str, target: str, detail: dict | None
) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target=target, detail=detail))


async def _get_game(db: AsyncSession, game_id: uuid.UUID) -> Game:
    game = await db.get(Game, game_id)
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在")
    return game


async def _owner_email(db: AsyncSession, owner_id: uuid.UUID) -> str | None:
    owner = await db.get(User, owner_id)
    return owner.email if owner else None


async def submit(
    db: AsyncSession, user: User, game_id: uuid.UUID, version: int, note: str | None
) -> PublishRequest:
    game = await _get_game(db, game_id)
    if game.owner_id != user.id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或不可见")
    if GameStatus(game.status) not in _SUBMITTABLE:
        raise AppError(ErrorCode.INVALID_STATE, "当前状态不可提交发布")
    gv = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if gv is None:
        raise AppError(ErrorCode.INVALID_STATE, "版本不存在")
    req = PublishRequest(
        game_id=game_id, version=version, status=PublishStatus.SUBMITTED.value, note=note
    )
    db.add(req)
    game.status = GameStatus.SUBMITTED.value
    await db.commit()
    await db.refresh(req)
    return req


async def list_queue(
    db: AsyncSession, status: PublishStatus | None
) -> list[tuple[PublishRequest, Game]]:
    stmt = select(PublishRequest, Game).join(Game, PublishRequest.game_id == Game.id)
    if status is not None:
        stmt = stmt.where(PublishRequest.status == status.value)
    else:
        stmt = stmt.where(PublishRequest.status.in_([s.value for s in _REVIEWABLE]))
    stmt = stmt.order_by(PublishRequest.created_at.desc())
    return [(req, game) for req, game in (await db.execute(stmt)).all()]


async def _get_request(db: AsyncSession, pr_id: uuid.UUID) -> PublishRequest:
    req = await db.get(PublishRequest, pr_id)
    if req is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "发布申请不存在")
    return req


async def approve(db: AsyncSession, admin: User, pr_id: uuid.UUID) -> tuple[PublishRequest, Game]:
    req = await _get_request(db, pr_id)
    if PublishStatus(req.status) not in _REVIEWABLE:
        raise AppError(ErrorCode.INVALID_STATE, "该申请不可审批")
    game = await _get_game(db, req.game_id)
    await game_services.assert_can_publish(db, game.owner_id)
    req.status = PublishStatus.APPROVED.value
    req.reviewer_id = admin.id
    req.reviewed_at = datetime.now(UTC)
    game.status = GameStatus.PUBLISHED.value
    game.slug = _gen_slug(game.title)
    game.published_at = datetime.now(UTC)
    await _audit(db, admin.id, "approve", str(pr_id), {"game_id": str(game.id)})
    await db.commit()
    await db.refresh(req)
    email = await _owner_email(db, game.owner_id)
    await notify_services.notify_user(
        db,
        game.owner_id,
        kind="publish_approved",
        title="你的游戏已通过审批并上架",
        body=f"《{game.title}》已发布：/play/{game.slug}",
        email=email,
    )
    return req, game


async def reject(
    db: AsyncSession, admin: User, pr_id: uuid.UUID, reason: str
) -> tuple[PublishRequest, Game]:
    req = await _get_request(db, pr_id)
    if PublishStatus(req.status) not in _REVIEWABLE:
        raise AppError(ErrorCode.INVALID_STATE, "该申请不可审批")
    game = await _get_game(db, req.game_id)
    req.status = PublishStatus.REJECTED.value
    req.reviewer_id = admin.id
    req.reviewed_at = datetime.now(UTC)
    req.reject_reason = reason
    game.status = GameStatus.REJECTED.value
    await _audit(db, admin.id, "reject", str(pr_id), {"game_id": str(game.id), "reason": reason})
    await db.commit()
    await db.refresh(req)
    email = await _owner_email(db, game.owner_id)
    await notify_services.notify_user(
        db,
        game.owner_id,
        kind="publish_rejected",
        title="你的游戏发布申请被驳回",
        body=f"《{game.title}》被驳回。理由：{reason}",
        email=email,
    )
    return req, game


async def take_down(
    db: AsyncSession, admin: User, game_id: uuid.UUID, reason: str
) -> Game:
    game = await _get_game(db, game_id)
    if GameStatus(game.status) != GameStatus.PUBLISHED:
        raise AppError(ErrorCode.INVALID_STATE, "仅已发布游戏可下架")
    game.status = GameStatus.TAKEN_DOWN.value
    await _audit(db, admin.id, "take_down", str(game_id), {"reason": reason})
    await db.commit()
    email = await _owner_email(db, game.owner_id)
    await notify_services.notify_user(
        db,
        game.owner_id,
        kind="take_down",
        title="你的游戏已被下架",
        body=f"《{game.title}》已下架。理由：{reason}",
        email=email,
    )
    return game
