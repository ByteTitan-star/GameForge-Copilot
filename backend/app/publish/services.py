"""发布审批工作流：submit / queue / approve / reject / take_down + 审计。

状态机见 docs/04。admin 操作（approve/reject/take_down）落 audit_logs。
slug 在 approve 时分配（全局唯一）。审批/下架发通知邮件。
"""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    """根据标题生成带随机后缀的唯一 slug。

    作用：审批通过时为游戏分配全局唯一 URL 标识。
    场景：approve 将游戏置为 published 时调用。
    参数：title - 游戏标题。
    返回：小写 slug 字符串；标题无字母数字时用 "game-{hex}"。
    """
    base = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    if not base:
        base = "game"
    return f"{base}-{uuid.uuid4().hex[:8]}"


async def _audit(
    db: AsyncSession, actor_id: uuid.UUID, action: str, target: str, detail: dict | None
) -> None:
    """写入一条发布流程相关的审计日志。

    作用：将 approve/reject/take_down 等操作记入 audit_logs。
    场景：publish 模块内各 admin 操作完成后调用。
    参数：db - 数据库会话；actor_id - 操作者 ID；action - 动作名；
    target - 目标标识；detail - 附加字段。
    返回：无。
    """
    db.add(AuditLog(actor_id=actor_id, action=action, target=target, detail=detail))


async def _get_game(db: AsyncSession, game_id: uuid.UUID) -> Game:
    """按 ID 获取游戏，不存在则抛错。

    作用：publish 流程内统一的 Game 加载与存在性校验。
    场景：submit、approve、take_down 等需要 game 行时调用。
    参数：db - 数据库会话；game_id - 游戏 ID。
    返回：Game 实例；不存在时抛 GAME_NOT_FOUND。
    """
    game = await db.get(Game, game_id)
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在")
    return game


async def _owner_email(db: AsyncSession, owner_id: uuid.UUID) -> str | None:
    """查询游戏 owner 的邮箱。

    作用：审批/下架后发通知邮件时获取收件人。
    场景：approve、reject、take_down、republish 完成后调用 notify_user。
    参数：db - 数据库会话；owner_id - 用户 ID。
    返回：邮箱字符串；用户不存在时返回 None。
    """
    owner = await db.get(User, owner_id)
    return owner.email if owner else None


async def submit(
    db: AsyncSession, user: User, game_id: uuid.UUID, version: int, note: str | None
) -> PublishRequest:
    """创作者提交游戏版本进入发布审核队列。

    作用：创建 PublishRequest 并将游戏状态置为 submitted。
    场景：POST 提交发布申请路由；游戏须为 draft/rejected/taken_down。
    参数：db - 数据库会话；user - 提交者；game_id - 游戏 ID；version - 版本号；note - 可选备注。
    返回：新建的 PublishRequest；并发重复提交抛 INVALID_STATE。
    """
    game = await _get_game(db, game_id)
    if game.owner_id != user.id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或不可见")
    if GameStatus(game.status) not in _SUBMITTABLE:
        raise AppError(ErrorCode.INVALID_STATE, "当前状态不可提交发布")
    gv = await db.scalar(
        select(GameVersion).where(GameVersion.game_id == game_id, GameVersion.version == version)
    )
    if gv is None:
        raise AppError(ErrorCode.INVALID_STATE, "版本不存在")
    req = PublishRequest(
        game_id=game_id, version=version, status=PublishStatus.SUBMITTED.value, note=note
    )
    db.add(req)
    game.status = GameStatus.SUBMITTED.value
    try:
        await db.commit()
    except IntegrityError:
        # 并发 submit TOCTOU 兜底：两个请求同时穿过 _SUBMITTABLE 检查，
        # 部分唯一索引（uq_publish_active_per_game）拦下第二条 → 409。
        await db.rollback()
        raise AppError(ErrorCode.INVALID_STATE, "该游戏已有待审核的发布申请") from None
    await db.refresh(req)
    return req


async def withdraw(db: AsyncSession, user: User, pr_id: uuid.UUID) -> PublishRequest:
    """owner 撤回自己的发布申请。

    作用：submitted/reviewing → withdrawn，游戏回 draft，释放唯一活跃申请名额。
    场景：POST 按 publish_request id 撤回；
    部分唯一索引 uq_publish_active_per_game 覆盖 submitted/reviewing。
    参数：db - 数据库会话；user - owner；pr_id - 发布申请 ID。
    返回：更新后的 PublishRequest；非 owner 或状态不可撤回时抛错。
    """
    req = await _get_request(db, pr_id)
    game = await _get_game(db, req.game_id)
    if game.owner_id != user.id:
        # 非-owner 不暴露存在性，与 _get_owned_game 语义一致
        raise AppError(ErrorCode.GAME_NOT_FOUND, "发布申请不存在")
    if PublishStatus(req.status) not in _REVIEWABLE:
        raise AppError(ErrorCode.INVALID_STATE, "该申请不可撤回")
    req.status = PublishStatus.WITHDRAWN.value
    req.reviewed_at = datetime.now(UTC)
    game.status = GameStatus.DRAFT.value
    await db.commit()
    await db.refresh(req)
    return req


async def withdraw_by_game(db: AsyncSession, user: User, game_id: uuid.UUID) -> PublishRequest:
    """owner 按 game_id 撤回当前待审核申请。

    作用：定位该 game 的 active pr（submitted/reviewing）后复用 withdraw。
    场景：前端卡片视角仅有 game_id 时的撤回入口。
    参数：db - 数据库会话；user - owner；game_id - 游戏 ID。
    返回：withdraw 的结果；无待审核申请时抛 INVALID_STATE。
    """
    game = await _get_game(db, game_id)
    if game.owner_id != user.id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或不可见")
    req = await db.scalar(
        select(PublishRequest).where(
            PublishRequest.game_id == game_id,
            PublishRequest.status.in_([s.value for s in _REVIEWABLE]),
        )
    )
    if req is None:
        raise AppError(ErrorCode.INVALID_STATE, "该游戏没有待审核的发布申请")
    return await withdraw(db, user, req.id)


async def list_queue(
    db: AsyncSession, status: PublishStatus | None
) -> list[tuple[PublishRequest, Game]]:
    """列出发布审核队列（申请 + 关联游戏）。

    作用：admin 审核台数据源，默认仅 submitted/reviewing。
    场景：GET /admin/publish-queue 路由调用。
    参数：db - 数据库会话；status - 可选状态过滤。
    返回：(PublishRequest, Game) 元组列表，按申请创建时间倒序。
    """
    stmt = select(PublishRequest, Game).join(Game, PublishRequest.game_id == Game.id)
    if status is not None:
        stmt = stmt.where(PublishRequest.status == status.value)
    else:
        stmt = stmt.where(PublishRequest.status.in_([s.value for s in _REVIEWABLE]))
    stmt = stmt.order_by(PublishRequest.created_at.desc())
    return [(req, game) for req, game in (await db.execute(stmt)).all()]


async def _get_request(db: AsyncSession, pr_id: uuid.UUID) -> PublishRequest:
    """按 ID 获取发布申请，不存在则抛错。

    作用：approve/reject/withdraw 等流程的统一加载入口。
    场景：publish 模块内需要 PublishRequest 行时调用。
    参数：db - 数据库会话；pr_id - 发布申请 ID。
    返回：PublishRequest 实例；不存在时抛 GAME_NOT_FOUND。
    """
    req = await db.get(PublishRequest, pr_id)
    if req is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "发布申请不存在")
    return req


async def approve(db: AsyncSession, admin: User, pr_id: uuid.UUID) -> tuple[PublishRequest, Game]:
    """管理员审批通过发布申请并上架游戏。

    作用：申请 approved、游戏 published、分配 slug、发通知与审计。
    场景：POST /admin/publish/{id}/approve 路由调用。
    参数：db - 数据库会话；admin - 审批人；pr_id - 发布申请 ID。
    返回：(PublishRequest, Game) 元组；不可审批状态时抛 INVALID_STATE。
    """
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
    """管理员驳回发布申请。

    作用：申请 rejected、游戏 rejected、记录理由并通知 owner。
    场景：POST /admin/publish/{id}/reject 路由调用。
    参数：db - 数据库会话；admin - 审批人；pr_id - 申请 ID；reason - 驳回理由。
    返回：(PublishRequest, Game) 元组。
    """
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


async def take_down(db: AsyncSession, admin: User, game_id: uuid.UUID, reason: str) -> Game:
    """管理员下架已发布游戏。

    作用：游戏状态 taken_down、记审计并通知 owner。
    场景：admin 手动下架或 scheduler 定时下架到期时调用。
    参数：db - 数据库会话；admin - 操作者；game_id - 游戏 ID；reason - 下架理由。
    返回：更新后的 Game；非 published 时抛 INVALID_STATE。
    """
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


async def republish(db: AsyncSession, admin: User, game_id: uuid.UUID, reason: str) -> Game:
    """重新上架已下架游戏。

    作用：taken_down → published，对称于 take_down，并通知 owner。
    场景：admin 手动上架或 scheduler 定时上架到期时调用。
    参数：db - 数据库会话；admin - 操作者；game_id - 游戏 ID；reason - 上架说明。
    返回：更新后的 Game；非 taken_down 时抛 INVALID_STATE。
    """
    game = await _get_game(db, game_id)
    if GameStatus(game.status) != GameStatus.TAKEN_DOWN:
        raise AppError(ErrorCode.INVALID_STATE, "仅已下架游戏可重新上架")
    game.status = GameStatus.PUBLISHED.value
    await _audit(db, admin.id, "republish", str(game_id), {"reason": reason})
    await db.commit()
    email = await _owner_email(db, game.owner_id)
    await notify_services.notify_user(
        db,
        game.owner_id,
        kind="republish",
        title="你的游戏已重新上架",
        body=f"《{game.title}》已重新上架：/play/{game.slug}",
        email=email,
    )
    return game
