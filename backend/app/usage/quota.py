"""每用户配额覆盖（Redis `quota:user:{uid}`）+ 日限额解析。

docs/05：全局默认 + 用户级覆盖；覆盖优先。
"""

import uuid

import redis.asyncio as redis

_KEY = "quota:user:{uid}"
_ALERT_KEY = "quota:alerted:{uid}:{date}"


def _key(user_id: uuid.UUID) -> str:
    return _KEY.format(uid=user_id)


async def set_user_daily_limit(
    r: redis.Redis, user_id: uuid.UUID, daily_limit: int | None
) -> None:
    """写入/清除用户日 token 上限覆盖。None = 删除覆盖，回退全局默认。"""
    key = _key(user_id)
    if daily_limit is None:
        await r.delete(key)
    else:
        await r.set(key, str(daily_limit))


async def get_user_daily_limit(
    r: redis.Redis, user_id: uuid.UUID, default: int
) -> int:
    raw = await r.get(_key(user_id))
    return int(raw) if raw is not None else default


async def mark_quota_alerted(r: redis.Redis, user_id: uuid.UUID, day: str) -> bool:
    """当日首次告警返回 True（可发邮件）；已告警过返回 False。"""
    key = _ALERT_KEY.format(uid=user_id, date=day)
    # SET NX：仅首次成功
    ok = await r.set(key, "1", nx=True, ex=86400)
    return bool(ok)
