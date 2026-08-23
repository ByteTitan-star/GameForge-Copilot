"""每用户配额覆盖（Redis `quota:user:{uid}`）+ 日限额解析。

docs/05：全局默认 + 用户级覆盖；覆盖优先。
"""

import uuid

import redis.asyncio as redis

_KEY = "quota:user:{uid}"
_ALERT_KEY = "quota:alerted:{uid}:{date}"


def _key(user_id: uuid.UUID) -> str:
    """生成用户日 token 限额覆盖的 Redis 键名。

    作用：quota:user:{uid} 存储 per-user 日限额整数。
    场景：set/get_user_daily_limit 读写覆盖值时调用。
    参数：user_id - 用户 ID。
    返回：Redis key 字符串。
    """
    return _KEY.format(uid=user_id)


async def set_user_daily_limit(r: redis.Redis, user_id: uuid.UUID, daily_limit: int | None) -> None:
    """写入或清除用户日 token 限额覆盖。

    作用：SET quota:user:{uid}；None 表示删除覆盖回退全局默认。
    场景：admin patch_user 设置 daily_token_limit 时调用。
    参数：r - Redis；user_id - 用户 ID；daily_limit - 限额整数或 None。
    返回：无。
    """
    key = _key(user_id)
    if daily_limit is None:
        await r.delete(key)
    else:
        await r.set(key, str(daily_limit))


async def get_user_daily_limit(r: redis.Redis, user_id: uuid.UUID, default: int) -> int:
    """读取用户日 token 限额（Redis 覆盖优先于全局 default）。

    场景：usage 扣减前解析当日上限。
    参数：r、user_id、default - 无覆盖时的全局默认。
    返回：日限额整数。
    """
    raw = await r.get(_key(user_id))
    return int(raw) if raw is not None else default


async def mark_quota_alerted(r: redis.Redis, user_id: uuid.UUID, day: str) -> bool:
    """当日首次告警返回 True（可发邮件）；已告警过返回 False。"""
    key = _ALERT_KEY.format(uid=user_id, date=day)
    # SET NX：仅首次成功
    ok = await r.set(key, "1", nx=True, ex=86400)
    return bool(ok)
