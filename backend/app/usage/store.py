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
    """生成用户当日用量 Redis hash 键名。

    作用：按 UTC 日期隔离日累计 token/calls。
    场景：record_usage 累加与 get_user_usage 读取时调用。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
    return f"usage:user:{user_id}:day:{datetime.now(UTC):%Y-%m-%d}"


def _month_key(user_id: uuid.UUID) -> str:
    """生成用户当月用量 Redis hash 键名。

    作用：按 UTC 年月隔离月累计与月榜关联。
    场景：record_usage 累加与配额/统计读取时调用。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
    return f"usage:user:{user_id}:month:{datetime.now(UTC):%Y-%m}"


def _total_key(user_id: uuid.UUID) -> str:
    """生成用户全量累计用量 Redis hash 键名。

    作用：存储用户历史总 input/output/calls，不过期。
    场景：record_usage 累加与 get_user_usage 读取 total 桶时调用。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
    return f"usage:user:{user_id}:total"


def _sys_day() -> str:
    """生成全站当日用量 Redis hash 键名。

    作用：聚合所有用户的日 token/calls 到系统级计数。
    场景：record_usage 写系统桶与 get_system_usage 读取时调用。
    参数：无。
    返回：Redis key 字符串。
    """
    return f"usage:sys:day:{datetime.now(UTC):%Y-%m-%d}"


def _sys_month() -> str:
    """生成全站当月用量 Redis hash 键名。

    作用：聚合所有用户的月 token/calls。
    场景：record_usage 与 get_system_usage 读取 month 桶时调用。
    参数：无。
    返回：Redis key 字符串。
    """
    return f"usage:sys:month:{datetime.now(UTC):%Y-%m}"


def _sys_total() -> str:
    """生成全站历史累计用量 Redis hash 键名。

    作用：存储系统级总 input/output/calls，不过期。
    场景：record_usage 与 get_system_usage 读取 total 桶时调用。
    参数：无。
    返回：Redis key 字符串。
    """
    return "usage:sys:total"


def _rank_key() -> str:
    """生成当月用户 token 月榜 ZSET 键名。

    作用：按用户月 token 总量排序，供 admin top users 查询。
    场景：record_usage zincrby 与 get_top_users zrevrange 时调用。
    参数：无。
    返回：Redis key 字符串。
    """
    return f"usage:rank:month:{datetime.now(UTC):%Y-%m}"


def _game_month_key(game_id: uuid.UUID) -> str:
    """生成单游戏当月用量 Redis hash 键名。

    作用：按 game 维度累计月 token/calls，供用量明细展示。
    场景：record_usage（带 game_id）与 get_game_usage 时调用。
    参数：game_id - 游戏 ID。
    返回：Redis key 字符串。
    """
    return f"usage:game:{game_id}:month:{datetime.now(UTC):%Y-%m}"


def _run_month_key(run_id: uuid.UUID) -> str:
    """生成单次 run 当月用量 Redis hash 键名。

    作用：按 generation_run 维度累计月 token/calls。
    场景：record_usage（带 run_id）与 get_run_usage 时调用。
    参数：run_id - 生成 run ID。
    返回：Redis key 字符串。
    """
    return f"usage:run:{run_id}:month:{datetime.now(UTC):%Y-%m}"


def _user_games_index(user_id: uuid.UUID) -> str:
    """生成用户当月有用量记录的游戏 ID 集合键名。

    作用：SET 索引，供 list_usage_breakdown scope=game 列举游戏。
    场景：record_usage 在提供 game_id 时 sadd。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
    return f"usage:user:{user_id}:games:{datetime.now(UTC):%Y-%m}"


def _user_runs_index(user_id: uuid.UUID) -> str:
    """生成用户当月有用量记录的 run ID 集合键名。

    作用：SET 索引，供 list_usage_breakdown scope=run 列举 run。
    场景：record_usage 在提供 run_id 时 sadd。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
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
    idempotency_key: str | None = None,
) -> bool:
    """累加 user/sys 及可选 game/run 的 token 用量。

    作用：Redis hash 累加 day/month/total、月榜 ZSET 与索引 SET；支持幂等门闩。
    场景：M4 LLM 层每次调用返回真实 usage 后调用。
    参数：r - Redis；user_id - 用户；input/output_tokens、calls - 计量值；
        game_id/run_id - 可选维度；idempotency_key - 可选幂等键。
    返回：成功记账 True；幂等键已存在则跳过并返回 False。
    """
    if idempotency_key is not None:
        from app.forge.reliability.idempotency import try_begin_side_effect

        if not await try_begin_side_effect(r, idempotency_key):
            return False

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
    return True


async def _bucket(r: redis.Redis, key: str) -> UsageBucket:
    """从 Redis hash 读取单个用量桶。

    作用：将 hash 字段解析为 UsageBucket schema。
    场景：get_user_usage、get_system_usage、get_top_users 等内部复用。
    参数：r - Redis；key - hash 键名。
    返回：UsageBucket 实例；缺字段默认为 0。
    """
    raw = await r.hgetall(key) or {}
    return UsageBucket(
        input_tokens=int(raw.get("input_tokens", 0)),
        output_tokens=int(raw.get("output_tokens", 0)),
        calls=int(raw.get("calls", 0)),
    )


async def get_user_usage(r: redis.Redis, user_id: uuid.UUID, daily_limit: int) -> UsageResp:
    """读取用户今日/本月/累计用量及日配额剩余。

    作用：组装 UsageResp，含 QuotaInfo 剩余额度。
    场景：GET /me/usage 路由调用。
    参数：r - Redis；user_id - 用户 ID；daily_limit - 生效日限额。
    返回：UsageResp 实例。
    """
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
    """读取全站今日/本月/累计 token 用量。

    作用：聚合系统级三个用量桶。
    场景：admin 用量面板与 get_admin_usage 调用。
    参数：r - Redis 客户端。
    返回：SystemUsage 实例。
    """
    return SystemUsage(
        today=await _bucket(r, _sys_day()),
        month=await _bucket(r, _sys_month()),
        total=await _bucket(r, _sys_total()),
    )


async def get_top_users(r: redis.Redis, db: AsyncSession, limit: int = 10) -> list[AdminUserUsage]:
    """查询月榜 top N 用户及其当月用量明细。

    作用：ZSET 月榜取 top → 各用户 month hash + DB 补 email。
    场景：get_admin_usage 组装 top_users 时调用。
    参数：r - Redis；db - 数据库会话；limit - 榜单条数，默认 10。
    返回：AdminUserUsage 列表。
    """
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
    """组装 admin 用量总览（系统 + top 用户）。

    作用：合并 get_system_usage 与 get_top_users。
    场景：GET /admin/usage 路由调用。
    参数：r - Redis；db - 数据库会话。
    返回：AdminUsageResp 实例。
    """
    return AdminUsageResp(system=await get_system_usage(r), top_users=await get_top_users(r, db))


async def get_game_usage(r: redis.Redis, game_id: uuid.UUID) -> UsageBucket:
    """读取单游戏当月 token 用量桶。

    作用：读取 usage:game:{id}:month:{ym} hash。
    场景：用量明细与 list_usage_breakdown scope=game 时调用。
    参数：r - Redis；game_id - 游戏 ID。
    返回：UsageBucket 实例。
    """
    return await _bucket(r, _game_month_key(game_id))


async def get_run_usage(r: redis.Redis, run_id: uuid.UUID) -> UsageBucket:
    """读取单次 run 当月 token 用量桶。

    作用：读取 usage:run:{id}:month:{ym} hash。
    场景：用量明细与 list_usage_breakdown scope=run 时调用。
    参数：r - Redis；run_id - 生成 run ID。
    返回：UsageBucket 实例。
    """
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
    """分页列出用户用量按游戏或 run 的拆分明细。

    作用：scope=game|run 时从索引 SET 列举 ID，附带 title 与 USD 估算。
    场景：GET /me/usage/breakdown 路由调用。
    参数：r - Redis；db - 数据库；user_id - 用户；scope - "game" 或 "run"；
        page/size - 分页；provider/model - 价表估算用。
    返回：(明细 dict 列表, 总条数)；非法 scope 返回空列表与 0。
    """
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
            (await db.scalars(select(GenerationRun).where(GenerationRun.id.in_(ids)))).all()
            if ids
            else []
        )
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
