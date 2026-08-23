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
    title_en: str
    description: str
    description_en: str
    requirement: str
    html_filename: str
    html_filename_en: str


OFFICIAL_CATALOG: tuple[OfficialGameSpec, ...] = (
    OfficialGameSpec(
        game_id=OFFICIAL_NEON_SNAKE_ID,
        slug="official-neon-snake",
        title="霓虹贪吃蛇",
        title_en="Neon Snake",
        description="方向键控制霓虹小蛇，吃豆得分，撞墙结束。",
        description_en="Steer a neon snake with arrow keys, eat orbs to score, and avoid walls.",
        requirement="霓虹风格贪吃蛇：方向键控制，吃食物变长，计分，撞墙 game over。",
        html_filename="neon_snake.html",
        html_filename_en="neon_snake_en.html",
    ),
    OfficialGameSpec(
        game_id=OFFICIAL_PIXEL_RUNNER_ID,
        slug="official-pixel-runner",
        title="像素跑酷",
        title_en="Pixel Runner",
        description="空格跳跃躲避障碍，像素风侧 scroll 跑酷。",
        description_en="Space to jump and dodge obstacles in a pixel side-scroller.",
        requirement="像素风横版跑酷：空格跳跃，躲避障碍，距离计分。",
        html_filename="pixel_runner.html",
        html_filename_en="pixel_runner_en.html",
    ),
    OfficialGameSpec(
        game_id=OFFICIAL_TOWER_STUB_ID,
        slug="official-tower-stub",
        title="塔防雏形",
        title_en="Tower Defense Stub",
        description="点击放置防御塔，拦截沿路径前进的小怪。",
        description_en="Place towers on the map to stop enemies marching along the path.",
        requirement="极简塔防：固定路径，点击放塔，拦截敌人波次。",
        html_filename="tower_stub.html",
        html_filename_en="tower_stub_en.html",
    ),
)

OFFICIAL_SLUGS = frozenset(s.slug for s in OFFICIAL_CATALOG)
_CATALOG_BY_SLUG = {s.slug: s for s in OFFICIAL_CATALOG}


def normalize_locale(locale: str | None) -> str:
    """归一化 locale 为 zh 或 en。

    作用：将任意 locale 字符串映射为 "zh"/"en"。
    场景：官方游戏标题/描述本地化。
    参数：locale — 请求 locale，缺省 zh。
    返回："zh" 或 "en"。
    """
    raw = (locale or "zh").strip().lower()
    return "en" if raw.startswith("en") else "zh"


def catalog_for_slug(slug: str | None) -> OfficialGameSpec | None:
    """按 slug 查找官方游戏规格。

    作用：从内置目录返回 OfficialGameSpec。
    场景：本地化标题、Fork 前校验。
    参数：slug — 官方游戏 slug。
    返回：规格对象；非官方 slug 返回 None。
    """
    if not slug:
        return None
    return _CATALOG_BY_SLUG.get(slug)


def localized_game_title(game: Game, locale: str | None = None) -> str:
    """返回本地化游戏标题。

    作用：官方游戏按 locale 取 catalog 标题，其余用 DB title。
    场景：公开列表、详情 API。
    参数：game — Game ORM；locale — 可选语言。
    返回：展示用标题字符串。
    """
    spec = catalog_for_slug(game.slug)
    if spec is None:
        return game.title
    loc = normalize_locale(locale)
    return spec.title_en if loc == "en" else spec.title


def localized_description(spec: OfficialGameSpec, locale: str | None = None) -> str:
    """返回官方游戏本地化描述。

    作用：按 locale 选择中/英描述字段。
    场景：官方游戏列表展示。
    参数：spec — 官方游戏规格；locale — 可选语言。
    返回：描述字符串。
    """
    loc = normalize_locale(locale)
    return spec.description_en if loc == "en" else spec.description


def assets_dir() -> Path:
    """返回官方 HTML 资产目录路径。

    作用：定位 scripts/official_assets 目录。
    场景：load_html、seed 写产物。
    参数：无。
    返回：资产目录 Path。
    """
    return Path(__file__).resolve().parents[2] / "scripts" / "official_assets"


def load_html(spec: OfficialGameSpec, locale: str | None = None) -> str:
    """读取官方游戏 HTML 源码。

    作用：按 locale 加载对应 html 文件，缺失时回退中文源。
    场景：seed_official_games 写产物。
    参数：spec — 官方游戏规格；locale — 可选语言。
    返回：HTML 文件 UTF-8 文本。
    """
    loc = normalize_locale(locale)
    filename = spec.html_filename_en if loc == "en" else spec.html_filename
    path = assets_dir() / filename
    if not path.exists():
        path = assets_dir() / spec.html_filename
    if not path.exists():
        raise FileNotFoundError(f"official asset missing: {path}")
    return path.read_text(encoding="utf-8")


async def ensure_official_user(db: AsyncSession) -> User:
    """幂等创建或返回官方账号用户。

    作用：按固定 OFFICIAL_OWNER_ID 确保官方 owner 存在。
    场景：seed_official_games 前置。
    参数：db — 数据库会话。
    返回：官方 User ORM 实例。
    """
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
            select(GameVersion).where(GameVersion.game_id == spec.game_id, GameVersion.version == 1)
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
        await write_artifact(
            spec.game_id,
            1,
            {
                "index.html": load_html(spec, "zh"),
                "index.en.html": load_html(spec, "en"),
            },
        )
    await db.commit()
    return SeedResult(created=created, refreshed=refreshed)


async def list_official_games(
    db: AsyncSession,
    locale: str | None = None,
) -> list[dict[str, str | None]]:
    """GET /official-games 数据。"""
    loc = normalize_locale(locale)
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
    return [
        {
            "slug": g.slug or "",
            "title": localized_game_title(g, loc),
            "description": localized_description(_CATALOG_BY_SLUG[g.slug or ""], loc)
            if g.slug in _CATALOG_BY_SLUG
            else (g.requirement[:120]),
            "play_url": f"/play/{g.slug}",
            "thumbnail_url": None,
        }
        for g in rows
    ]


async def get_official_game(db: AsyncSession, slug: str) -> Game:
    """获取已发布的官方预置游戏。

    作用：校验 slug 属于官方目录且 owner 为官方账号。
    场景：Fork、公开试玩。
    参数：db — 会话；slug — 官方游戏 slug。
    返回：Game ORM 实例。
    """
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
    """统计用户草稿游戏数量。

    作用：Fork 前草稿配额校验。
    场景：fork_official_game。
    参数：db — 会话；user_id — 用户 ID。
    返回：draft 状态游戏数。
    """
    from sqlalchemy import func

    n = await db.scalar(
        select(func.count())
        .select_from(Game)
        .where(Game.owner_id == user_id, Game.status == GameStatus.DRAFT.value)
    )
    return int(n or 0)


def _copy_artifact(src_game_id: uuid.UUID, dst_game_id: uuid.UUID, version: int) -> None:
    """复制产物目录到新游戏。

    作用：将源游戏版本产物整目录复制到目标路径。
    场景：Fork 官方游戏时复制 HTML 产物。
    参数：src_game_id — 源游戏 ID；dst_game_id — 目标游戏 ID；version — 版本号。
    返回：无；源目录不存在则跳过。
    """
    src = artifact_dir(src_game_id, version)
    dst = artifact_dir(dst_game_id, version)
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


async def fork_official_game(db: AsyncSession, user: User, slug: str) -> Game:
    """将官方游戏 Fork 为当前用户草稿。

    作用：复制 requirement、版本与产物到新 draft 游戏。
    场景：POST /games/fork/{slug}。
    参数：db — 会话；user — 当前用户；slug — 官方游戏 slug。
    返回：新建 draft Game ORM 实例。
    """
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
