"""游戏点赞/收藏（Batch C · R7）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, ReactionType
from app.models.game import Game
from app.models.game_reaction import GameReaction
from app.models.user import User
from app.profile import services as profile_services
from app.schemas.reactions import (
    CreatorBrief,
    PublicGameMeta,
    ReactionStateResp,
    ReactionToggleResp,
)


async def _get_published_game(db: AsyncSession, game_id: UUID) -> Game:
    game = await db.scalar(
        select(Game).where(Game.id == game_id, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    return game


async def reaction_counts(db: AsyncSession, game_id: UUID) -> tuple[int, int]:
    likes = await db.scalar(
        select(func.count())
        .select_from(GameReaction)
        .where(
            GameReaction.game_id == game_id,
            GameReaction.type == ReactionType.LIKE.value,
        )
    )
    favorites = await db.scalar(
        select(func.count())
        .select_from(GameReaction)
        .where(
            GameReaction.game_id == game_id,
            GameReaction.type == ReactionType.FAVORITE.value,
        )
    )
    return int(likes or 0), int(favorites or 0)


async def toggle_reaction(
    db: AsyncSession, user: User, game_id: UUID, reaction_type: ReactionType
) -> ReactionToggleResp:
    await _get_published_game(db, game_id)
    row = await db.scalar(
        select(GameReaction).where(
            GameReaction.user_id == user.id,
            GameReaction.game_id == game_id,
            GameReaction.type == reaction_type.value,
        )
    )
    if row is not None:
        await db.delete(row)
        active = False
    else:
        db.add(
            GameReaction(user_id=user.id, game_id=game_id, type=reaction_type.value)
        )
        active = True
    await db.commit()
    like_count, favorite_count = await reaction_counts(db, game_id)
    return ReactionToggleResp(
        game_id=game_id,
        active=active,
        like_count=like_count,
        favorite_count=favorite_count,
    )


async def get_reaction_state(
    db: AsyncSession, user: User, game_id: UUID
) -> ReactionStateResp:
    """当前用户对该游戏的点赞/收藏态 + 公开计数（游戏须 published）。"""
    await _get_published_game(db, game_id)
    reacted = {
        t
        for t in await db.scalars(
            select(GameReaction.type).where(
                GameReaction.user_id == user.id,
                GameReaction.game_id == game_id,
            )
        )
    }
    like_count, favorite_count = await reaction_counts(db, game_id)
    return ReactionStateResp(
        game_id=game_id,
        liked=ReactionType.LIKE.value in reacted,
        favorited=ReactionType.FAVORITE.value in reacted,
        like_count=like_count,
        favorite_count=favorite_count,
    )


async def remove_reaction(
    db: AsyncSession, user: User, game_id: UUID, reaction_type: ReactionType
) -> ReactionToggleResp:
    """幂等删除当前用户的指定 reaction（不存在则 noop），返回最新计数。"""
    await _get_published_game(db, game_id)
    row = await db.scalar(
        select(GameReaction).where(
            GameReaction.user_id == user.id,
            GameReaction.game_id == game_id,
            GameReaction.type == reaction_type.value,
        )
    )
    if row is not None:
        await db.delete(row)
        await db.commit()
    like_count, favorite_count = await reaction_counts(db, game_id)
    return ReactionToggleResp(
        game_id=game_id,
        active=False,
        like_count=like_count,
        favorite_count=favorite_count,
    )


async def _public_game_meta(db: AsyncSession, game: Game) -> PublicGameMeta:
    """收藏列表与公开广场共用同一公开元数据形状（无 owner PII）。"""
    handle, display_name = await profile_services.get_owner_brief(db, game.owner_id)
    like_count, favorite_count = await reaction_counts(db, game.id)
    return PublicGameMeta(
        game_id=game.id,
        title=game.title,
        slug=game.slug or "",
        cover_url=(
            f"/play/{game.slug}/thumb.png" if game.cover_path and game.slug else None
        ),
        published_at=game.published_at,
        play_count=game.play_count,
        like_count=like_count,
        favorite_count=favorite_count,
        creator=CreatorBrief(handle=handle, display_name=display_name),
    )


async def list_favorites(
    db: AsyncSession, user: User, page: int, size: int
) -> tuple[list[PublicGameMeta], int]:
    base = (
        select(GameReaction, Game)
        .join(Game, Game.id == GameReaction.game_id)
        .where(
            GameReaction.user_id == user.id,
            GameReaction.type == ReactionType.FAVORITE.value,
        )
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.execute(
            base.order_by(GameReaction.created_at.desc())
            .limit(size)
            .offset((page - 1) * size)
        )
    ).all()
    items = [await _public_game_meta(db, game) for _reaction, game in rows]
    return items, int(total or 0)
