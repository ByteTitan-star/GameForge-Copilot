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
from app.schemas.reactions import FavoriteGameItem, ReactionToggleResp


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


async def list_favorites(
    db: AsyncSession, user: User, page: int, size: int
) -> tuple[list[FavoriteGameItem], int]:
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
    items = [
        FavoriteGameItem(
            game_id=game.id,
            title=game.title,
            slug=game.slug or "",
            status=GameStatus(game.status),
            play_count=game.play_count,
            favorited_at=reaction.created_at,
        )
        for reaction, game in rows
    ]
    return items, int(total or 0)
