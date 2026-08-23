"""游戏点赞/收藏（Batch C · R7）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.trial import reject_trial_mutation
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, ReactionType
from app.games import official as official_svc
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
    """获取已发布游戏，不存在或未发布则抛错。

    作用：reaction 操作前的游戏可见性校验。
    场景：toggle_reaction、get_reaction_state 等入口。
    参数：db — 数据库会话；game_id — 游戏 ID。
    返回：Game 实例；不存在或未 published 时抛 GAME_NOT_FOUND。
    """
    game = await db.scalar(
        select(Game).where(Game.id == game_id, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    return game


async def reaction_counts(db: AsyncSession, game_id: UUID) -> tuple[int, int]:
    """统计游戏的点赞数与收藏数。

    作用：分别 count LIKE 与 FAVORITE 类型的 GameReaction。
    场景：toggle/remove 后返回最新计数、公开元数据组装。
    参数：db — 数据库会话；game_id — 游戏 ID。
    返回：(like_count, favorite_count) 元组。
    """
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
    """切换用户对游戏的点赞或收藏状态。

    作用：已存在则删除（取消），不存在则创建；试用账号只读。
    场景：公开试玩页点赞/收藏按钮。
    参数：db — 数据库会话；user — 当前用户；game_id — 游戏 ID；reaction_type — LIKE 或 FAVORITE。
    返回：ReactionToggleResp，含 active 状态与最新计数。
    """
    reject_trial_mutation(user)
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
        db.add(GameReaction(user_id=user.id, game_id=game_id, type=reaction_type.value))
        active = True
    await db.commit()
    like_count, favorite_count = await reaction_counts(db, game_id)
    return ReactionToggleResp(
        game_id=game_id,
        active=active,
        like_count=like_count,
        favorite_count=favorite_count,
    )


async def get_reaction_state(db: AsyncSession, user: User, game_id: UUID) -> ReactionStateResp:
    """查询当前用户对该游戏的点赞/收藏态及公开计数。

    作用：返回 liked/favorited 布尔值与全站 like/favorite 计数。
    场景：试玩页加载 reaction 状态。
    参数：db — 数据库会话；user — 当前用户；game_id — 游戏 ID。
    返回：ReactionStateResp；游戏须 published。
    """
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
    """幂等删除当前用户的指定 reaction。

    作用：不存在则 noop；存在则删除并返回最新计数。
    场景：取消点赞/收藏 API。
    参数：db — 数据库会话；user — 当前用户；game_id — 游戏 ID；reaction_type — 类型。
    返回：ReactionToggleResp，active=False 与最新计数。
    """
    reject_trial_mutation(user)
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
    """组装公开游戏元数据（收藏列表与广场共用）。

    作用：合并标题、slug、封面、播放数、creator 摘要与 reaction 计数。
    场景：list_favorites、公开广场列表项。
    参数：db — 数据库会话；game — 已发布 Game 行。
    返回：PublicGameMeta 实例（不含 owner PII）。
    """
    handle, display_name = await profile_services.get_owner_brief(db, game.owner_id)
    like_count, favorite_count = await reaction_counts(db, game.id)
    title = official_svc.localized_game_title(game)
    return PublicGameMeta(
        game_id=game.id,
        title=title,
        slug=game.slug or "",
        cover_url=(f"/play/{game.slug}/thumb.png" if game.cover_path and game.slug else None),
        published_at=game.published_at,
        play_count=game.play_count,
        featured=game.featured_rank is not None,
        like_count=like_count,
        favorite_count=favorite_count,
        creator=CreatorBrief(handle=handle, display_name=display_name),
    )


async def list_favorites(
    db: AsyncSession, user: User, page: int, size: int
) -> tuple[list[PublicGameMeta], int]:
    """分页列出用户收藏的游戏公开元数据。

    作用：join GameReaction 与 Game，按收藏时间倒序。
    场景：list_favorites API 与 GET /me/favorites 路由。
    参数：db — 数据库会话；user — 当前用户；page/size — 分页。
    返回：(PublicGameMeta 列表, 总条数) 元组。
    """
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
            base.order_by(GameReaction.created_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    items = [await _public_game_meta(db, game) for _reaction, game in rows]
    return items, int(total or 0)
