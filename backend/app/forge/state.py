"""run 检查点：Redis 存 JSON 状态，支持 HITL 中断后恢复。docs/03 §检查点。"""

import json
import uuid

import redis.asyncio as redis

_KEY = "run:ckpt:{run_id}"


async def save_state(r: redis.Redis, run_id: uuid.UUID, state: dict) -> None:
    await r.set(_KEY.format(run_id=run_id), json.dumps(state, ensure_ascii=False))


async def load_state(r: redis.Redis, run_id: uuid.UUID) -> dict | None:
    raw = await r.get(_KEY.format(run_id=run_id))
    return json.loads(raw) if raw else None


async def clear_state(r: redis.Redis, run_id: uuid.UUID) -> None:
    await r.delete(_KEY.format(run_id=run_id))
