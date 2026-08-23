"""用户公开资料与创作者主页（Batch C · R6）。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.trial import reject_trial_mutation
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus
from app.models.game import Game
from app.models.user import User
from app.schemas.profile import CreatorGameItem, CreatorProfile, ProfilePatch, UserProfile


def _to_profile(user: User) -> UserProfile:
    """将 User ORM 行转为 UserProfile 响应模型。

    作用：字段映射与序列化。
    场景：get_profile、patch_profile 组装响应。
    参数：user — 用户数据库行。
    返回：UserProfile Pydantic 模型。
    """
    return UserProfile(
        user_id=user.id,
        email=user.email,
        handle=user.handle,
        display_name=user.display_name,
        profile_public=user.profile_public,
    )


async def get_profile(db: AsyncSession, user: User) -> UserProfile:
    """读取当前用户资料。

    作用：返回昵称、handle、头像公开设置等字段。
    场景：GET /me/profile 路由调用。
    参数：db — 数据库会话；user — 当前用户。
    返回：UserProfile 实例。
    """
    return _to_profile(user)


async def patch_profile(db: AsyncSession, user: User, req: ProfilePatch) -> UserProfile:
    """部分更新用户资料。

    作用：修改 display_name、handle、profile_public；试用账号只读。
    场景：PATCH /me/profile 路由调用。
    参数：db — 数据库会话；user — 当前用户；req — 待更新字段。
    返回：更新后的 UserProfile；handle 冲突 409，试用账号 403。
    """
    reject_trial_mutation(user)
    if req.handle is not None:
        existing = await db.scalar(
            select(User).where(User.handle == req.handle, User.id != user.id)
        )
        if existing is not None:
            raise AppError(ErrorCode.HANDLE_TAKEN, "handle 已被占用")
        user.handle = req.handle
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.profile_public is not None:
        user.profile_public = req.profile_public
    await db.commit()
    await db.refresh(user)
    return _to_profile(user)


async def get_public_creator(db: AsyncSession, handle: str) -> CreatorProfile:
    """按 handle 获取公开创作者主页数据。

    作用：返回公开资料、已发布游戏列表与播放统计。
    场景：GET /u/{handle} 路由调用。
    参数：db — 数据库会话；handle — 创作者唯一标识。
    返回：CreatorProfile 实例；未公开或不存在时抛 GAME_NOT_FOUND。
    """
    user = await db.scalar(select(User).where(User.handle == handle))
    if user is None or not user.profile_public:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "创作者不存在或未公开")
    games = (
        await db.scalars(
            select(Game)
            .where(Game.owner_id == user.id, Game.status == GameStatus.PUBLISHED.value)
            .order_by(Game.published_at.desc())
        )
    ).all()
    total_plays = sum(g.play_count for g in games)
    latest: datetime | None = None
    if games:
        latest = max((g.published_at for g in games if g.published_at), default=None)
    return CreatorProfile(
        handle=user.handle or handle,
        display_name=user.display_name,
        total_plays=total_plays,
        latest_published_at=latest,
        games=[
            CreatorGameItem(
                game_id=g.id,
                title=g.title,
                slug=g.slug or "",
                play_count=g.play_count,
                published_at=g.published_at,
            )
            for g in games
        ],
    )


async def get_owner_brief(db: AsyncSession, owner_id) -> tuple[str | None, str | None]:
    """查询游戏 owner 的公开标识摘要。

    作用：返回 handle 与 display_name，不含邮箱等 PII。
    场景：公开游戏元数据、收藏列表组装 creator 字段。
    参数：db — 数据库会话；owner_id — 用户 ID。
    返回：(handle, display_name) 元组；用户不存在时均为 None。
    """
    user = await db.get(User, owner_id)
    if user is None:
        return None, None
    return user.handle, user.display_name
