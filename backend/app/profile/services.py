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
    return UserProfile(
        user_id=user.id,
        email=user.email,
        handle=user.handle,
        display_name=user.display_name,
        profile_public=user.profile_public,
    )


async def get_profile(db: AsyncSession, user: User) -> UserProfile:
    return _to_profile(user)


async def patch_profile(db: AsyncSession, user: User, req: ProfilePatch) -> UserProfile:
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
    user = await db.get(User, owner_id)
    if user is None:
        return None, None
    return user.handle, user.display_name
