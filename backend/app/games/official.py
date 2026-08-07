"""官方预置游戏：常量、列表、Fork（Batch A · B-A1/B-A2）。"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, Role
from app.hosting.local import artifact_dir, write_artifact
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.user import User

# 固定官方账号（seed 与运行时识别）
OFFICIAL_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-000000000001")
OFFICIAL_OWNER_EMAIL = "official@gameforge.internal"


@dataclass(frozen=True)
class OfficialGameSpec:
    slug: str
    title: str
    description: str
    requirement: str
    html_filename: str


OFFICIAL_CATALOG: tuple[OfficialGameSpec, ...] = (
    OfficialGameSpec(
        slug="official-neon-snake",
        title="霓虹贪吃蛇",
        description="方向键控制霓虹小蛇，吃豆得分，撞墙结束。",
        requirement="霓虹风格贪吃蛇：方向键控制，吃食物变长，计分，撞墙 game over。",
        html_filename="neon_snake.html",
    ),
    OfficialGameSpec(
        slug="official-pixel-runner",
        title="像素跑酷",
        description="空格跳跃躲避障碍，像素风侧 scroll 跑酷。",
        requirement="像素风横版跑酷：空格跳跃，躲避障碍，距离计分。",
        html_filename="pixel_runner.html",
    ),
    OfficialGameSpec(
        slug="official-tower-stub",
        title="塔防雏形",
        description="点击放置防御塔，拦截沿路径前进的小怪。",
        requirement="极简塔防：固定路径，点击放塔，拦截敌人波次。",
        html_filename="tower_stub.html",
    ),
)

OFFICIAL_SLUGS = frozenset(s.slug for s in OFFICIAL_CATALOG)


def assets_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "scripts" / "official_assets"


def load_html(spec: OfficialGameSpec) -> str:
    path = assets_dir() / spec.html_filename
    if not path.exists():
        raise FileNotFoundError(f"official asset missing: {path}")
    return path.read_text(encoding="utf-8")


async def ensure_official_user(db: AsyncSession) -> User:
    user = await db.get(User, OFFICIAL_OWNER_ID)
    if user is not None:
        return user
    user = User(
        id=OFFICIAL_OWNER_ID,
        email=OFFICIAL_OWNER_EMAIL,
        password_hash=hash_password("official-not-for-login"),
        role=Role.USER.value,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def seed_official_games(db: AsyncSession) -> int:
    """幂等写入官方 published 游戏，返回新建数量。"""
    owner = await ensure_official_user(db)
    created = 0
    now = datetime.now(UTC)
    for spec in OFFICIAL_CATALOG:
        existing = await db.scalar(select(Game).where(Game.slug == spec.slug))
        if existing is not None:
            continue
        html = load_html(spec)
        game = Game(
            owner_id=owner.id,
            slug=spec.slug,
            title=spec.title,
            requirement=spec.requirement,
            status=GameStatus.PUBLISHED.value,
            current_version=1,
            published_at=now,
            play_count=0,
        )
        db.add(game)
        await db.flush()
        artifact_path = f"{game.id}/1/index.html"
        db.add(
            GameVersion(
                game_id=game.id,
                version=1,
                artifact_path=artifact_path,
                design_doc={
                    "title": spec.title,
                    "gameplay": spec.requirement,
                    "controls": "见游戏内说明",
                    "levels": [],
                },
            )
        )
        await write_artifact(game.id, 1, {"index.html": html})
        created += 1
    await db.commit()
    return created


async def list_official_games(db: AsyncSession) -> list[dict[str, str | None]]:
    """GET /official-games 数据。"""
    rows = (
        await db.scalars(
            select(Game)
            .where(
                Game.slug.in_(OFFICIAL_SLUGS),
                Game.status == GameStatus.PUBLISHED.value,
            )
            .order_by(Game.slug)
        )
    ).all()
    desc_by_slug = {s.slug: s.description for s in OFFICIAL_CATALOG}
    return [
        {
            "slug": g.slug or "",
            "title": g.title,
            "description": desc_by_slug.get(g.slug or "", g.requirement[:120]),
            "play_url": f"/play/{g.slug}",
            "thumbnail_url": None,
        }
        for g in rows
    ]


async def get_official_game(db: AsyncSession, slug: str) -> Game:
    if slug not in OFFICIAL_SLUGS:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "官方游戏不存在")
    game = await db.scalar(
        select(Game).where(
            Game.slug == slug,
            Game.status == GameStatus.PUBLISHED.value,
            Game.owner_id == OFFICIAL_OWNER_ID,
        )
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "官方游戏不存在")
    return game


async def _count_drafts(db: AsyncSession, user_id: uuid.UUID) -> int:
    from sqlalchemy import func

    n = await db.scalar(
        select(func.count())
        .select_from(Game)
        .where(Game.owner_id == user_id, Game.status == GameStatus.DRAFT.value)
    )
    return int(n or 0)


def _copy_artifact(src_game_id: uuid.UUID, dst_game_id: uuid.UUID, version: int) -> None:
    src = artifact_dir(src_game_id, version)
    dst = artifact_dir(dst_game_id, version)
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


async def fork_official_game(db: AsyncSession, user: User, slug: str) -> Game:
    from app.games.services import _require_verified

    _require_verified(user)
    if await _count_drafts(db, user.id) >= settings.max_drafts_per_user:
        raise AppError(
            ErrorCode.QUOTA_EXCEEDED,
            f"草稿游戏数已达上限（{settings.max_drafts_per_user}）",
        )
    src = await get_official_game(db, slug)
    src_version = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == src.id, GameVersion.version == src.current_version
        )
    )
    title = f"{src.title}（副本）"
    game = Game(
        owner_id=user.id,
        title=title,
        requirement=src.requirement,
        status=GameStatus.DRAFT.value,
        current_version=1 if src_version else 0,
    )
    db.add(game)
    await db.flush()
    if src_version and src.current_version >= 1:
        artifact_path = f"{game.id}/1/index.html"
        db.add(
            GameVersion(
                game_id=game.id,
                version=1,
                artifact_path=artifact_path,
                design_doc=src_version.design_doc,
            )
        )
        _copy_artifact(src.id, game.id, src.current_version)
    await db.commit()
    await db.refresh(game)
    return game
