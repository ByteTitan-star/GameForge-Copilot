"""token 用量计量：Redis hash 累计 + ZSET 月榜。

docs/05：只用 LLM 响应真实 usage，不估算。key 设计见 docs/05 表。
M4 LLM 层每次调用后调 record_usage；本模块也提供读取供 /me/usage、/admin/usage。
"""

import uuid
from datetime import UTC, datetime

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.usage import (
    AdminUsageResp,
    AdminUserUsage,
    QuotaInfo,
    SystemUsage,
    UsageBucket,
    UsageResp,
)


def _day_key(user_id: uuid.UUID) -> str:
    return f"usage:user:{user_id}:day:{datetime.now(UTC):%Y-%m-%d}"


def _month_key(user_id: uuid.UUID) -> str:
    return f"usage:user:{user_id}:month:{datetime.now(UTC):%Y-%m}"


def _total_key(user_id: uuid.UUID) -> str:
    return f"usage:user:{user_id}:total"


def _sys_day() -> str:
    return f"usage:sys:day:{datetime.now(UTC):%Y-%m-%d}"


def _sys_month() -> str:
    return f"usage:sys:month:{datetime.now(UTC):%Y-%m}"


def _sys_total() -> str:
    return "usage:sys:total"


def _rank_key() -> str:
    return f"usage:rank:month:{datetime.now(UTC):%Y-%m}"


def _game_month_key(game_id: uuid.UUID) -> str:
    return f"usage:game:{game_id}:month:{datetime.now(UTC):%Y-%m}"


def _run_month_key(run_id: uuid.UUID) -> str:
    return f"usage:run:{run_id}:month:{datetime.now(UTC):%Y-%m}"


def _user_games_index(user_id: uuid.UUID) -> str:
    return f"usage:user:{user_id}:games:{datetime.now(UTC):%Y-%m}"


def _user_runs_index(user_id: uuid.UUID) -> str:
    return f"usage:user:{user_id}:runs:{datetime.now(UTC):%Y-%m}"


async def record_usage(
    r: redis.Redis,
    user_id: uuid.UUID,
    *,
    input_tokens: int,
    output_tokens: int,
    calls: int = 1,
    game_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
) -> None:
    """M4 LLM 层调用：累加 user/sys 的 day/month/total + 月榜 ZSET。一次 pipeline。

    day/month key 设 TTL（只增数据不无限堆积），total 不设。
    可选 game_id/run_id 维度（B3）。
    """
    total = input_tokens + output_tokens
    uid = str(user_id)
    pipe = r.pipeline()
    # (key, ttl_seconds)；total 不过期
    user_keys = (
        (_day_key(user_id), 7 * 86400),
        (_month_key(user_id), 40 * 86400),
        (_total_key(user_id), None),
    )
    sys_keys = (
        (_sys_day(), 7 * 86400),
        (_sys_month(), 40 * 86400),
        (_sys_total(), None),
    )
    extra: list[tuple[str, int | None]] = []
    if game_id is not None:
        extra.append((_game_month_key(game_id), 40 * 86400))
    if run_id is not None:
        extra.append((_run_month_key(run_id), 40 * 86400))
    for key, ttl in (*user_keys, *sys_keys, *extra):
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        pipe.hincrby(key, "calls", calls)
        if ttl is not None:
            pipe.expire(key, ttl)
    pipe.zincrby(_rank_key(), total, uid)
    if game_id is not None:
        idx = _user_games_index(user_id)
        pipe.sadd(idx, str(game_id))
        pipe.expire(idx, 40 * 86400)
    if run_id is not None:
        idx = _user_runs_index(user_id)
        pipe.sadd(idx, str(run_id))
        pipe.expire(idx, 40 * 86400)
    await pipe.execute()


async def _bucket(r: redis.Redis, key: str) -> UsageBucket:
    raw = await r.hgetall(key) or {}
    return UsageBucket(
        input_tokens=int(raw.get("input_tokens", 0)),
        output_tokens=int(raw.get("output_tokens", 0)),
        calls=int(raw.get("calls", 0)),
    )


async def get_user_usage(
    r: redis.Redis, user_id: uuid.UUID, daily_limit: int
) -> UsageResp:
    today = await _bucket(r, _day_key(user_id))
    month = await _bucket(r, _month_key(user_id))
    total = await _bucket(r, _total_key(user_id))
    daily_used = today.input_tokens + today.output_tokens
    return UsageResp(
        today=today,
        month=month,
        total=total,
        quota=QuotaInfo(
            daily_token_limit=daily_limit,
            daily_used=daily_used,
            remaining=max(0, daily_limit - daily_used),
        ),
    )


async def get_system_usage(r: redis.Redis) -> SystemUsage:
    return SystemUsage(
        today=await _bucket(r, _sys_day()),
        month=await _bucket(r, _sys_month()),
        total=await _bucket(r, _sys_total()),
    )


async def get_top_users(
    r: redis.Redis, db: AsyncSession, limit: int = 10
) -> list[AdminUserUsage]:
    """月榜 ZSET top N → 各用户 month hash 拆分 + DB 取 email。"""
    ranked = await r.zrevrange(_rank_key(), 0, limit - 1, withscores=True)
    if not ranked:
        return []
    uids: list[tuple[uuid.UUID, float]] = [(uuid.UUID(m), s) for m, s in ranked]
    rows = (await db.scalars(select(User).where(User.id.in_([u for u, _ in uids])))).all()
    email_by_id = {u.id: u.email for u in rows}
    result: list[AdminUserUsage] = []
    for uid, _score in uids:
        month = await _bucket(r, _month_key(uid))
        result.append(
            AdminUserUsage(
                user_id=uid,
                email=email_by_id.get(uid, ""),
                month_input_tokens=month.input_tokens,
                month_output_tokens=month.output_tokens,
                calls=month.calls,
            )
        )
    return result


async def get_admin_usage(r: redis.Redis, db: AsyncSession) -> AdminUsageResp:
    return AdminUsageResp(
        system=await get_system_usage(r), top_users=await get_top_users(r, db)
    )


async def get_game_usage(r: redis.Redis, game_id: uuid.UUID) -> UsageBucket:
    return await _bucket(r, _game_month_key(game_id))


async def get_run_usage(r: redis.Redis, run_id: uuid.UUID) -> UsageBucket:
    return await _bucket(r, _run_month_key(run_id))


async def list_usage_breakdown(
    r: redis.Redis,
    db: AsyncSession,
    user_id: uuid.UUID,
    scope: str,
    page: int,
    size: int,
    *,
    provider: str = "openai_compat",
    model: str = "default",
) -> tuple[list[dict], int]:
    """scope=game|run → [{ id, title?, ...tokens, estimated_usd }]"""
    from app.models.game import Game
    from app.models.generation_run import GenerationRun
    from app.usage.pricing import estimate_usd

    if scope == "game":
        idx = _user_games_index(user_id)
        ids_raw = await r.smembers(idx)
        ids = [uuid.UUID(x) for x in ids_raw]
        rows = (await db.scalars(select(Game).where(Game.id.in_(ids)))).all() if ids else []
        title_map = {g.id: g.title for g in rows}
        items: list[tuple[uuid.UUID, UsageBucket, str | None]] = []
        for gid in ids:
            b = await get_game_usage(r, gid)
            if b.calls == 0 and b.input_tokens == 0:
                continue
            items.append((gid, b, title_map.get(gid)))
    elif scope == "run":
        idx = _user_runs_index(user_id)
        ids_raw = await r.smembers(idx)
        ids = [uuid.UUID(x) for x in ids_raw]
        runs = (
            await db.scalars(select(GenerationRun).where(GenerationRun.id.in_(ids)))
        ).all() if ids else []
        title_by_run: dict[uuid.UUID, str | None] = {}
        if runs:
            gids = {run.game_id for run in runs}
            games = (await db.scalars(select(Game).where(Game.id.in_(gids)))).all()
            gt = {g.id: g.title for g in games}
            for run in runs:
                title_by_run[run.id] = gt.get(run.game_id)
        items = []
        for rid in ids:
            b = await get_run_usage(r, rid)
            if b.calls == 0 and b.input_tokens == 0:
                continue
            items.append((rid, b, title_by_run.get(rid)))
    else:
        return [], 0

    items.sort(key=lambda x: x[1].input_tokens + x[1].output_tokens, reverse=True)
    total = len(items)
    start = (page - 1) * size
    page_items = items[start : start + size]
    out: list[dict] = []
    for eid, bucket, title in page_items:
        out.append(
            {
                "id": eid,
                "title": title,
                "input_tokens": bucket.input_tokens,
                "output_tokens": bucket.output_tokens,
                "calls": bucket.calls,
                "estimated_usd": round(
                    estimate_usd(
                        provider,
                        model,
                        input_tokens=bucket.input_tokens,
                        output_tokens=bucket.output_tokens,
                    ),
                    6,
                ),
            }
        )
    return out, total
