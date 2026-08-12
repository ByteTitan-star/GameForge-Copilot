"""游戏与 run 的 CRUD 业务逻辑：可见性 owner 过滤（docs/06 强制，admin 不可见草稿）。

路由薄，逻辑聚此。run 执行（forge runner）与发布（M7）分离。
含并发 run 上限、草稿/已发布数上限、版本保留上限（docs/04/05）。
"""

from datetime import UTC, datetime
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import services as admin_services
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import EntryPhase, GameStatus, RunPhase, RunStatus
from app.forge import control as run_ctrl
from app.forge import state as ckpt
from app.forge.entry_router import classify_entry_phase
from app.hosting import store as hosting_store
from app.messaging.outbox import add_task, cancel_run_tasks
from app.messaging.tasks import (
    TASK_EXECUTE_RUN,
    TASK_RESUME_RUN,
    resume_payload,
    run_id_payload,
)
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.generation_run import GenerationRun
from app.models.llm_config import UserLLMConfig
from app.models.user import User
from app.schemas.game import GameCreate, GamePatch
from app.schemas.run import RunCreate
from app.usage import quota as quota_mod
from app.usage.store import get_user_usage

_DELETABLE = {GameStatus.DRAFT, GameStatus.REJECTED, GameStatus.TAKEN_DOWN}
_ACTIVE_RUNS = {RunStatus.RUNNING, RunStatus.PAUSED}
_RENAMEABLE = {GameStatus.DRAFT, GameStatus.REJECTED, GameStatus.TAKEN_DOWN}


def _require_verified(user: User) -> None:
    if not user.email_verified:
        raise AppError(ErrorCode.EMAIL_NOT_VERIFIED, "邮箱未验证，无法创建游戏或发起 run")


async def _get_owned_game(db: AsyncSession, user: User, game_id: UUID) -> Game:
    game = await db.scalar(
        select(Game).where(Game.id == game_id, Game.owner_id == user.id)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或不可见")
    return game


async def get_owned_game(db: AsyncSession, user: User, game_id: UUID) -> Game:
    return await _get_owned_game(db, user, game_id)


async def _count_games(db: AsyncSession, user_id: UUID, status: GameStatus) -> int:
    n = await db.scalar(
        select(func.count())
        .select_from(Game)
        .where(Game.owner_id == user_id, Game.status == status.value)
    )
    return int(n or 0)


async def create_game(db: AsyncSession, user: User, req: GameCreate) -> Game:
    _require_verified(user)
    title = (req.title or "").strip()
    requirement = (req.requirement or "").strip()
    if req.template_id:
        from app.forge.templates.loader import get_template

        tpl = get_template(req.template_id)
        if not title:
            title = str(tpl["title"])
        if not requirement:
            requirement = str(tpl["requirement_seed"])
    if not title or not requirement:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "title 与 requirement 必填（或使用 template_id）",
        )
    drafts = await _count_games(db, user.id, GameStatus.DRAFT)
    if drafts >= settings.max_drafts_per_user:
        raise AppError(
            ErrorCode.QUOTA_EXCEEDED,
            f"草稿游戏数已达上限（{settings.max_drafts_per_user}）",
        )
    game = Game(
        owner_id=user.id,
        title=title,
        requirement=requirement,
        status=GameStatus.DRAFT.value,
        current_version=0,
    )
    db.add(game)
    await db.commit()
    await db.refresh(game)
    return game


async def list_games(
    db: AsyncSession, user: User, status: GameStatus | None, page: int, size: int
) -> tuple[list[Game], int]:
    base = select(Game).where(Game.owner_id == user.id)
    if status is not None:
        base = base.where(Game.status == status.value)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(Game.updated_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def list_public_games(
    db: AsyncSession,
    page: int,
    size: int,
    sort: str = "updated_at",
) -> tuple[list[Game], int]:
    """公开已发布游戏列表（无 PII，admin 草稿不可见）。"""
    base = select(Game).where(Game.status == GameStatus.PUBLISHED.value)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    order = Game.play_count.desc() if sort == "play_count" else Game.updated_at.desc()
    rows = (
        await db.scalars(base.order_by(order).limit(size).offset((page - 1) * size))
    ).all()
    return list(rows), int(total or 0)


async def list_featured_games(
    db: AsyncSession,
    page: int,
    size: int,
) -> tuple[list[Game], int]:
    """本周精选：published 且 featured_rank 非空，按 rank 升序。"""
    base = select(Game).where(
        Game.status == GameStatus.PUBLISHED.value,
        Game.featured_rank.is_not(None),
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(Game.featured_rank.asc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def get_public_game_by_slug(db: AsyncSession, slug: str) -> Game:
    game = await db.scalar(
        select(Game).where(Game.slug == slug, Game.status == GameStatus.PUBLISHED.value)
    )
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在或未发布")
    return game


async def get_game_detail(
    db: AsyncSession, user: User, game_id: UUID
) -> tuple[Game, list[GameVersion]]:
    game = await _get_owned_game(db, user, game_id)
    versions = (
        await db.scalars(
            select(GameVersion).where(GameVersion.game_id == game_id).order_by(GameVersion.version)
        )
    ).all()
    return game, list(versions)


async def patch_game(db: AsyncSession, user: User, game_id: UUID, req: GamePatch) -> Game:
    """草稿重命名（docs/01 MVP）。"""
    game = await _get_owned_game(db, user, game_id)
    if GameStatus(game.status) not in _RENAMEABLE:
        raise AppError(ErrorCode.INVALID_STATE, "当前状态不可修改标题")
    if req.title is not None:
        title = req.title.strip()
        if not title:
            raise AppError(ErrorCode.VALIDATION_ERROR, "标题不能为空")
        game.title = title
    await db.commit()
    await db.refresh(game)
    return game


async def delete_game(db: AsyncSession, user: User, game_id: UUID) -> Game:
    game = await _get_owned_game(db, user, game_id)
    if GameStatus(game.status) not in _DELETABLE:
        raise AppError(ErrorCode.INVALID_STATE, "当前状态不可删除")
    await db.delete(game)
    await db.commit()
    return game


async def delete_games(
    db: AsyncSession, user: User, game_ids: list[UUID]
) -> tuple[list[UUID], list[tuple[UUID, str]]]:
    """批量删除：逐个按 owner + 可删状态校验，部分失败不中断。

    返回 (deleted_ids, failed) — failed 每项为 (game_id, reason)。
    单事务提交：已通过校验的删除一起持久化，被拒的记入 failed。
    """
    deleted: list[UUID] = []
    failed: list[tuple[UUID, str]] = []
    games: dict[UUID, Game] = {}
    for gid in game_ids:
        game = await db.scalar(select(Game).where(Game.id == gid, Game.owner_id == user.id))
        if game is None:
            failed.append((gid, "游戏不存在或不可见"))
            continue
        if GameStatus(game.status) not in _DELETABLE:
            failed.append((gid, "当前状态不可删除，请先下架或撤回"))
            continue
        games[gid] = game
    for game in games.values():
        await db.delete(game)
        deleted.append(game.id)
    if deleted:
        await db.commit()
    return deleted, failed


async def unpublish_own_game(db: AsyncSession, user: User, game_id: UUID) -> Game:
    """owner 自助下架已发布游戏：published → taken_down。

    与 admin take_down 区分：owner 走自己的仓库视图，无需审批原因。
    下架后清掉 featured_rank（已下架不应再占据精选位）。
    """
    game = await _get_owned_game(db, user, game_id)
    if GameStatus(game.status) != GameStatus.PUBLISHED:
        raise AppError(ErrorCode.INVALID_STATE, "仅已发布游戏可下架")
    game.status = GameStatus.TAKEN_DOWN.value
    game.featured_rank = None
    await db.commit()
    await db.refresh(game)
    return game


async def list_versions(db: AsyncSession, user: User, game_id: UUID) -> list[GameVersion]:
    await _get_owned_game(db, user, game_id)
    rows = (
        await db.scalars(
            select(GameVersion).where(GameVersion.game_id == game_id).order_by(GameVersion.version)
        )
    ).all()
    return list(rows)


async def get_owned_version(
    db: AsyncSession, user: User, game_id: UUID, version: int
) -> tuple[Game, GameVersion]:
    """Return one version only after verifying ownership to avoid leaking its existence."""
    game = await _get_owned_game(db, user, game_id)
    row = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if row is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "版本不存在")
    return game, row


async def prune_old_versions(db: AsyncSession, game: Game) -> None:
    """保留最近 max_versions_per_game 个版本，删除更旧的 DB 行与产物目录。"""
    rows = (
        await db.scalars(
            select(GameVersion)
            .where(GameVersion.game_id == game.id)
            .order_by(GameVersion.version.desc())
        )
    ).all()
    keep = settings.max_versions_per_game
    if len(rows) <= keep:
        return
    for old in rows[keep:]:
        base = hosting_store.artifact_dir(game.id, old.version)
        if base.exists():
            import shutil

            shutil.rmtree(base, ignore_errors=True)
        await db.delete(old)
    await db.commit()


async def create_run(
    db: AsyncSession,
    r: redis.Redis,
    user: User,
    game_id: UUID,
    req: RunCreate,
    client_request_id: str | None = None,
) -> GenerationRun:
    _require_verified(user)
    game = await _get_owned_game(db, user, game_id)

    # 串行化同一用户的 run 创建：吸收双击/重复提交，并消除并发数计数的 TOCTOU。
    # 锁仅在创建期间持有（毫秒级，create_run 本身不跑 LLM）；进程崩溃则 10s 后自动释放。
    lock_key = f"run:create:{user.id}"
    if not await r.set(lock_key, "1", nx=True, ex=10):
        raise AppError(ErrorCode.RATE_LIMITED, "请勿重复发起 run，稍后再试")
    try:
        if client_request_id:
            existing = await db.scalar(
                select(GenerationRun).where(
                    GenerationRun.user_id == user.id,
                    GenerationRun.client_request_id == client_request_id,
                )
            )
            if existing is not None:
                return existing
        active = await db.scalar(
            select(func.count())
            .select_from(GenerationRun)
            .where(
                GenerationRun.user_id == user.id,
                GenerationRun.status.in_([s.value for s in _ACTIVE_RUNS]),
            )
        )
        if int(active or 0) >= settings.max_concurrent_runs:
            raise AppError(
                ErrorCode.RATE_LIMITED,
                f"同时进行的 run 已达上限（{settings.max_concurrent_runs}）",
            )

        daily_default, monthly_default, _ = await admin_services.get_effective_limits(db)
        daily = await quota_mod.get_user_daily_limit(r, user.id, daily_default)
        usage = await get_user_usage(r, user.id, daily)
        if usage.quota.remaining <= 0:
            raise AppError(ErrorCode.QUOTA_EXCEEDED, "今日 token 配额已耗尽")
        month_used = usage.month.input_tokens + usage.month.output_tokens
        if month_used >= monthly_default:
            raise AppError(ErrorCode.QUOTA_EXCEEDED, "本月 token 配额已耗尽")

        # 默认配置路径：未显式指定 llm_config_id 时必须有 is_default 配置，否则 run 带病入队
        if req.llm_config_id is None:
            has_default = await db.scalar(
                select(UserLLMConfig.id)
                .where(
                    UserLLMConfig.user_id == user.id,
                    UserLLMConfig.is_default.is_(True),
                )
                .limit(1)
            )
            if has_default is None:
                raise AppError(
                    ErrorCode.LLM_CONFIG_INVALID,
                    "尚未配置默认 LLM，请先在「设置 → LLM 配置」中添加并设为默认。",
                )
        if req.llm_config_id is not None:
            cfg = await db.scalar(
                select(UserLLMConfig).where(
                    UserLLMConfig.id == req.llm_config_id,
                    UserLLMConfig.user_id == user.id,
                )
            )
            if cfg is None:
                raise AppError(ErrorCode.LLM_CONFIG_NOT_FOUND, "LLM 配置不存在")
        entry = classify_entry_phase(
            req.requirement, has_prior_version=game.current_version > 0
        )
        initial_phase = RunPhase.CODE if entry == EntryPhase.CODE else RunPhase.PLAN
        run = GenerationRun(
            game_id=game.id,
            user_id=user.id,
            llm_config_id=req.llm_config_id,
            requirement=req.requirement,
            client_request_id=client_request_id,
            entry_phase=entry.value,
            status=RunStatus.RUNNING.value,
            phase=initial_phase.value,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        await db.flush()
        await add_task(db, TASK_EXECUTE_RUN, run_id_payload(run.id))
        await db.commit()
        await db.refresh(run)
        return run
    finally:
        await r.delete(lock_key)


async def list_runs(
    db: AsyncSession, user: User, game_id: UUID
) -> list[GenerationRun]:
    await _get_owned_game(db, user, game_id)
    rows = (
        await db.scalars(
            select(GenerationRun)
            .where(GenerationRun.game_id == game_id)
            .order_by(GenerationRun.started_at.desc())
        )
    ).all()
    return list(rows)


async def list_user_active_runs(
    db: AsyncSession, user: User, limit: int = 20
) -> list[tuple[GenerationRun, Game]]:
    """跨游戏进行中的 run（running / paused），供刷新后找回任务。"""
    rows = (
        await db.execute(
            select(GenerationRun, Game)
            .join(Game, Game.id == GenerationRun.game_id)
            .where(
                GenerationRun.user_id == user.id,
                GenerationRun.status.in_(
                    [RunStatus.RUNNING.value, RunStatus.PAUSED.value]
                ),
            )
            .order_by(GenerationRun.started_at.desc())
            .limit(limit)
        )
    ).all()
    return [(run, game) for run, game in rows]


async def get_run(db: AsyncSession, user: User, run_id: UUID) -> GenerationRun:
    run = await db.scalar(
        select(GenerationRun).where(
            GenerationRun.id == run_id, GenerationRun.user_id == user.id
        )
    )
    if run is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "run 不存在或不可见")
    return run


async def pause_run(
    db: AsyncSession, r: redis.Redis, user: User, run_id: UUID
) -> GenerationRun:
    run = await get_run(db, user, run_id)
    if run.status != RunStatus.RUNNING.value:
        raise AppError(ErrorCode.INVALID_STATE, "仅 running 可暂停")
    await run_ctrl.request_pause(r, run_id)
    run.status = RunStatus.PAUSED.value
    await db.commit()
    await db.refresh(run)
    return run


async def resume_run_control(
    db: AsyncSession, r: redis.Redis, user: User, run_id: UUID
) -> GenerationRun:
    """用户续跑：从检查点继续（HITL 或主动 pause）。"""
    run = await get_run(db, user, run_id)
    if run.status != RunStatus.PAUSED.value:
        raise AppError(ErrorCode.INVALID_STATE, "仅 paused 可续跑")
    await ckpt.load_state(r, run_id, db)
    await run_ctrl.clear_control(r, run_id)
    run.status = RunStatus.RUNNING.value
    run.ended_at = None
    await add_task(db, TASK_RESUME_RUN, resume_payload(run_id, "approve", None))
    await db.commit()
    await db.refresh(run)
    return run


async def cancel_run(
    db: AsyncSession, r: redis.Redis, user: User, run_id: UUID
) -> GenerationRun:
    run = await get_run(db, user, run_id)
    if run.status not in (RunStatus.RUNNING.value, RunStatus.PAUSED.value):
        raise AppError(ErrorCode.INVALID_STATE, "仅进行中的 run 可取消")
    await run_ctrl.request_cancel(r, run_id)
    run.status = RunStatus.FAILED.value
    run.ended_at = datetime.now(UTC)
    await cancel_run_tasks(db, run_id)
    await db.commit()
    await ckpt.clear_state(r, run_id, db)
    await db.commit()
    await r.delete(f"run:hitl:{run_id}")  # 清掉 HITL 并发锁，避免残留 resolve 重新触发已取消的 run
    await db.refresh(run)
    return run


async def assert_can_publish(db: AsyncSession, owner_id: UUID) -> None:
    """审批通过前：已发布数未超上限。"""
    n = await _count_games(db, owner_id, GameStatus.PUBLISHED)
    if n >= settings.max_published_per_user:
        raise AppError(
            ErrorCode.QUOTA_EXCEEDED,
            f"已发布游戏数已达上限（{settings.max_published_per_user}）",
        )


_ACTIVATABLE = {
    GameStatus.DRAFT,
    GameStatus.REJECTED,
    GameStatus.TAKEN_DOWN,
    GameStatus.PUBLISHED,
}
_RETRY_PHASES = frozenset({"sandbox_failed", "qa_failed"})


async def activate_version(
    db: AsyncSession, user: User, game_id: UUID, version: int
) -> Game:
    """切换 current_version（Batch A · B-A6）。"""
    game = await _get_owned_game(db, user, game_id)
    if GameStatus(game.status) not in _ACTIVATABLE:
        raise AppError(ErrorCode.INVALID_STATE, "当前状态不可切换版本")
    gv = await db.scalar(
        select(GameVersion).where(
            GameVersion.game_id == game_id, GameVersion.version == version
        )
    )
    if gv is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "版本不存在")
    game.current_version = version
    if isinstance(gv.design_doc, dict):
        gameplay = gv.design_doc.get("gameplay") or gv.design_doc.get("design")
        if isinstance(gameplay, str) and gameplay.strip():
            game.requirement = gameplay.strip()
    await db.commit()
    await db.refresh(game)
    return game


async def retry_run(
    db: AsyncSession, r: redis.Redis, user: User, run_id: UUID
) -> GenerationRun:
    """从失败检查点重试（Batch A · B-A5）。"""
    run = await get_run(db, user, run_id)
    st = await ckpt.load_state(r, run_id, db) or {}
    phase = st.get("phase")
    if phase not in _RETRY_PHASES:
        raise AppError(ErrorCode.INVALID_STATE, "当前 run 不可重试")
    if run.status not in (RunStatus.FAILED.value, RunStatus.PAUSED.value):
        raise AppError(ErrorCode.INVALID_STATE, "当前 run 不可重试")
    await run_ctrl.clear_control(r, run_id)
    await r.delete(f"run:hitl:{run_id}")
    run.status = RunStatus.RUNNING.value
    run.phase = RunPhase.CODE.value
    run.ended_at = None
    await add_task(db, TASK_RESUME_RUN, resume_payload(run_id, "approve", None))
    await db.commit()
    await db.refresh(run)
    return run
