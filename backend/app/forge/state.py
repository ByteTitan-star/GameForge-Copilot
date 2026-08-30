"""Run checkpoint persistence.

PostgreSQL is the durable source of truth. Redis remains a best-effort cache so a
Redis restart cannot discard an in-progress HITL interaction.
Cache payload includes revision so load_state can reject stale Redis phantoms (ADR-10).

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
本模块 = Forge Run 的「续跑游标」读写：
  - PG run_checkpoints：权威、每 run 一行最新 state（JSON dict）
  - Redis run:ckpt:{run_id}：带 revision 的最佳努力缓存
  - 不是按节点存历史栈；revision 用于防脏缓存，不是 time-travel
"""

import json  # Redis 存字符串：把 dict 序列化成 JSON
import logging  # 缓存失败只打日志，不拖垮有 DB 的路径
import uuid  # run_id 类型
from typing import Any

import redis.asyncio as redis  # 异步 Redis 客户端
from sqlalchemy.ext.asyncio import AsyncSession  # 异步 DB 会话（事务由调用方 commit）

from app.models.run_checkpoint import RunCheckpoint  # ORM：run_id PK + state + revision

_KEY = "run:ckpt:{run_id}"  # Redis key 模板；每个 run 一个 key
log = logging.getLogger(__name__)


def _cache_payload(revision: int, state: dict[str, Any]) -> str:
    """把「版本号 + 状态」打成 Redis 要存的 JSON 字符串。"""
    return json.dumps(
        {"revision": int(revision), "state": state},  # 必须带 revision，供 load 比对
        ensure_ascii=False,  # 保留中文可读，不转 \uXXXX
    )


def _parse_cache(raw: str | bytes) -> tuple[int | None, dict[str, Any] | None]:
    """解析 Redis 读出的原始值 → (revision, state)；失败返回 (None, None)。"""
    try:
        data = json.loads(raw)  # 反序列化
    except (TypeError, json.JSONDecodeError):
        return None, None  # 坏 JSON / 非字符串 → 当缓存无效
    # 新格式：{"revision": N, "state": {...}}
    if isinstance(data, dict) and "state" in data and "revision" in data:
        state = data.get("state")
        if isinstance(state, dict):
            try:
                return int(data["revision"]), state  # 正常路径：版本 + 状态 dict
            except (TypeError, ValueError):
                return None, None  # revision 无法转 int
    # 旧格式兼容：Redis 里直接存了裸 state dict（没有 revision 包装）
    if isinstance(data, dict):
        return None, data  # revision=None，load 时会与 DB 比对后以 DB 为准并回填
    return None, None  # 其它类型一律丢弃


async def save_state(
    r: redis.Redis,  # Redis 连接
    run_id: uuid.UUID,  # 本次 generation run
    state: dict,  # 要持久化的完整 checkpoint dict（整份覆盖，非字段 patch）
    db: AsyncSession | None = None,  # 有 DB 则写 PG；仅 Redis 时 db=None
) -> None:
    """写入 checkpoint：先 flush PG（权威），再 SET Redis（缓存）。不 commit——由调用方事务提交。"""
    revision = 1  # 无 DB 或新建时的默认版本号
    if db is not None:
        from app.models.generation_run import GenerationRun  # 延迟导入，避免循环依赖

        run = await db.get(GenerationRun, run_id)  # 取 run 行（可能不存在）
        # 已结束的 run 禁止再改 checkpoint（防终态后脏写）
        if run is not None and run.ended_at is not None:
            return
        row = await db.get(RunCheckpoint, run_id)  # 每 run 最多一行
        if row is None:
            # 首次：插入新行，revision 从 1 起
            row = RunCheckpoint(run_id=run_id, state=state, revision=1)
            db.add(row)
        else:
            row.state = state  # 整份覆盖最新快照
            row.revision += 1  # 版本自增：让 Redis 旧缓存对不上
        revision = int(row.revision)  # 后面写 Redis 用同一 revision
        if run is not None:
            # 方便排查：run 上挂一个指向 DB checkpoint 的引用字符串
            run.checkpoint_ref = f"db:run_checkpoints:{run_id}"
        await db.flush()  # SQL 发到连接，但仍在同一事务内；真正落盘靠外层 commit
    try:
        # 缓存结构：{"revision": N, "state": {...}}
        await r.set(_KEY.format(run_id=run_id), _cache_payload(revision, state))
    except Exception:
        if db is None:
            # 没有 DB 兜底时，Redis 失败必须抛出（否则状态彻底丢）
            raise
        # 有 PG 权威时：缓存失败只告警，不阻断主路径
        log.warning("checkpoint cache write failed run_id=%s", run_id, exc_info=True)


async def load_state(
    r: redis.Redis,  # Redis 连接
    run_id: uuid.UUID,  # 本次 generation run
    db: AsyncSession | None = None,  # 有 DB 则与 revision 比对；无则只信 Redis
) -> dict | None:
    """读取 checkpoint：优先用「revision 与 DB 一致」的 Redis；否则以 DB 为准并回填缓存。"""
    try:
        raw = await r.get(_KEY.format(run_id=run_id))  # 可能 None（未写过 / 过期）
    except Exception:
        raw = None  # 读缓存失败先当未命中
        if db is None:
            raise  # 无 DB 时 Redis 是唯一来源，必须失败上抛
        log.warning("checkpoint cache read failed run_id=%s", run_id, exc_info=True)

    cached_rev: int | None = None  # 缓存里的版本；旧格式为 None
    cached_state: dict[str, Any] | None = None  # 缓存里的 state
    if raw:
        cached_rev, cached_state = _parse_cache(raw)  # 解析失败则两者保持 None

    if db is None:
        return cached_state  # 无 DB：能解析多少返回多少

    row = await db.get(RunCheckpoint, run_id)  # PG 权威行
    if row is None:
        return cached_state  # DB 尚无行：退回缓存（冷启动/仅写过 Redis 的边缘情况）

    db_state = dict(row.state)  # 拷贝一份，避免调用方原地改 ORM 里的 JSON
    db_rev = int(row.revision)  # DB 当前版本
    # 缓存命中且 revision 一致 → 可直接用缓存（少一次大 JSON 当唯一来源的不确定）
    if cached_state is not None and cached_rev == db_rev:
        return cached_state

    # Redis 缺失、旧格式、或 revision 不一致 → 以 DB 为准（防幻影 grant / 脏缓存）
    try:
        await r.set(_KEY.format(run_id=run_id), _cache_payload(db_rev, db_state))  # 回填正确缓存
    except Exception:
        log.warning("checkpoint cache refill failed run_id=%s", run_id, exc_info=True)
    return db_state  # 始终返回权威状态


async def clear_state(r: redis.Redis, run_id: uuid.UUID, db: AsyncSession | None = None) -> None:
    """清除该 run 的 checkpoint（DB 行 + Redis key）；flush 仍不 commit。"""
    if db is not None:
        row = await db.get(RunCheckpoint, run_id)
        if row is not None:
            await db.delete(row)  # 删 PG 行
        from app.models.generation_run import GenerationRun

        run = await db.get(GenerationRun, run_id)
        if run is not None:
            run.checkpoint_ref = None  # 清掉 run 上的引用标记
        await db.flush()  # 事务内生效，等待外层 commit
    try:
        await r.delete(_KEY.format(run_id=run_id))  # 删缓存 key
    except Exception:
        if db is None:
            raise  # 无 DB：删除失败必须上抛
        log.warning("checkpoint cache delete failed run_id=%s", run_id, exc_info=True)
