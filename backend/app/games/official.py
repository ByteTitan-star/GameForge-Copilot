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

# 固定官方游戏 ID：避免每次重建 DB 拿随机 UUID，导致 .hosting/{id}/ 产物漂移成孤儿。
# 与 OFFICIAL_OWNER_ID 同一命名空间（...0000000000ax），一眼可辨是 seed 写入的官方行。
OFFICIAL_NEON_SNAKE_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a1")
OFFICIAL_PIXEL_RUNNER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a2")
OFFICIAL_TOWER_STUB_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a3")


@dataclass(frozen=True)
class OfficialGameSpec:
    game_id: uuid.UUID
    slug: str
    title: str
    description: str
    requirement: str
    html_filename: str


OFFICIAL_CATALOG: tuple[OfficialGameSpec, ...] = (
    OfficialGameSpec(
        game_id=OFFICIAL_NEON_SNAKE_ID,
        slug="official-neon-snake",
        title="霓虹贪吃蛇",
        description="方向键控制霓虹小蛇，吃豆得分，撞墙结束。",
        requirement="霓虹风格贪吃蛇：方向键控制，吃食物变长，计分，撞墙 game over。",
        html_filename="neon_snake.html",
    ),
    OfficialGameSpec(
        game_id=OFFICIAL_PIXEL_RUNNER_ID,
        slug="official-pixel-runner",
        title="像素跑酷",
        description="空格跳跃躲避障碍，像素风侧 scroll 跑酷。",
        requirement="像素风横版跑酷：空格跳跃，躲避障碍，距离计分。",
        html_filename="pixel_runner.html",
    ),
    OfficialGameSpec(
        game_id=OFFICIAL_TOWER_STUB_ID,
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


@dataclass(frozen=True)
class SeedResult:
    """seed 执行结果：created=新建（含自愈重建），refreshed=已存在并刷新产物。"""

    created: int
    refreshed: int


async def seed_official_games(db: AsyncSession) -> SeedResult:
    """幂等 upsert 官方 published 游戏，返回新建/刷新计数。

    固定 spec.game_id，使 .hosting/{id}/ 产物不随 DB 重建漂移成孤儿：
      - 不存在 → 按 spec.game_id 创建 + 写产物（计入 created）；
      - 存在但 id 非固定值（历史随机 UUID）→ 删旧行 + 旧产物，按固定 id 重建（计入 created）；
      - 存在且 id 匹配 → 同步 title/requirement + 始终从源重写产物（计入 refreshed）。
    故「created 0, refreshed 3」= 三款已就位、产物已按源刷新，属正常稳态。
    """
    owner = await ensure_official_user(db)
    created = 0
    refreshed = 0
    now = datetime.now(UTC)
    for spec in OFFICIAL_CATALOG:
        game = await db.scalar(select(Game).where(Game.slug == spec.slug))
        if game is not None and game.id != spec.game_id:
            # 历史随机 UUID：清掉旧行 + 旧产物，下面按固定 id 重建。
            stale_dir = artifact_dir(game.id, 1)
            await db.delete(game)  # ON DELETE CASCADE 连带 game_versions
            await db.commit()
            shutil.rmtree(stale_dir, ignore_errors=True)
            game = None
        if game is None:
            game = Game(
                id=spec.game_id,
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
            created += 1
        else:
            game.title = spec.title
            game.requirement = spec.requirement
            refreshed += 1
        design_doc = {
            "title": spec.title,
            "gameplay": spec.requirement,
            "controls": "见游戏内说明",
            "levels": [],
        }
        version = await db.scalar(
            select(GameVersion).where(
                GameVersion.game_id == spec.game_id, GameVersion.version == 1
            )
        )
        if version is None:
            db.add(
                GameVersion(
                    game_id=spec.game_id,
                    version=1,
                    artifact_path=f"{spec.game_id}/1/index.html",
                    design_doc=design_doc,
                )
            )
        else:
            version.design_doc = design_doc
        # 始终从源重写产物：编辑 scripts/official_assets 后重跑 seed 即更新线上试玩。
        await write_artifact(spec.game_id, 1, {"index.html": load_html(spec)})
    await db.commit()
    return SeedResult(created=created, refreshed=refreshed)


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
