"""#158：checkpoint 缓存读写路径（commit-then-cache + 廉价 revision 校验）。

验收点：
1. 命中且 revision 一致时，load_state 不得加载完整 state 行（仅 revision 列）。
2. flush 后回滚：Redis 不得携带未提交状态（幻影防护）。
3. save 后 clear 同事务：commit 后不得把已删除 state 写回 Redis。
4. Redis 不可用时 save/load 仍可靠 Postgres 工作。
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.forge import state as ckpt
from app.models.run_checkpoint import RunCheckpoint


def _key(run_id: uuid.UUID) -> str:
    return f"run:ckpt:{run_id}"


class _DeadRedis:
    """模拟不可用 Redis：所有操作抛连接错误。"""

    async def get(self, *a, **k):
        raise ConnectionError("redis down")

    async def set(self, *a, **k):
        raise ConnectionError("redis down")

    async def delete(self, *a, **k):
        raise ConnectionError("redis down")


async def test_load_state_cache_hit_skips_full_state_load(
    db_session: AsyncSession, redis_client
) -> None:
    run_id = uuid.uuid4()
    state = {"phase": "plan_confirm", "payload": "x" * 128}
    db_session.add(RunCheckpoint(run_id=run_id, state=state, revision=2))
    await db_session.commit()
    await redis_client.set(_key(run_id), ckpt._cache_payload(2, state))

    captured: list[str] = []
    sync_engine = db_session.get_bind()  # AsyncSession.get_bind 返回同步 Engine

    def _capture(conn, cursor, statement, params, context, executemany):
        if "run_checkpoints" in statement:
            captured.append(" ".join(statement.split()))

    event.listen(sync_engine, "before_cursor_execute", _capture)
    try:
        # 命中且 revision 一致 → 不得走 db.get 全量加载分支
        db_session.get = AsyncMock(side_effect=AssertionError("full row load must not happen"))
        loaded = await ckpt.load_state(redis_client, run_id, db_session)
    finally:
        event.remove(sync_engine, "before_cursor_execute", _capture)

    assert loaded == state
    assert len(captured) == 1, f"expect single checkpoint query, got: {captured}"
    assert "revision" in captured[0]
    assert "state" not in captured[0], f"query must not select state column: {captured[0]}"


async def test_save_state_publishes_cache_only_after_commit(
    db_session: AsyncSession, redis_client
) -> None:
    run_id = uuid.uuid4()
    state = {"phase": "code"}
    await ckpt.save_state(redis_client, run_id, state, db_session)
    # flush 后、commit 前：Redis 不得出现（commit-then-cache）
    assert await redis_client.get(_key(run_id)) is None

    await db_session.commit()
    await asyncio.sleep(0)  # 让 after_commit 发布任务获得调度
    raw = await redis_client.get(_key(run_id))
    assert raw is not None
    assert ckpt._parse_cache(raw) == (1, state)


async def test_rollback_after_flush_keeps_cache_behind_db(
    db_session: AsyncSession, redis_client
) -> None:
    run_id = uuid.uuid4()
    committed = {"phase": "plan_confirm", "v": 1}
    db_session.add(RunCheckpoint(run_id=run_id, state=committed, revision=1))
    await db_session.commit()
    await redis_client.set(_key(run_id), ckpt._cache_payload(1, committed))

    await ckpt.save_state(redis_client, run_id, {"phase": "plan_confirm", "v": 2}, db_session)
    await db_session.rollback()
    await asyncio.sleep(0)

    # 回滚后 Redis 只能落后（保留旧值或缺失），不得领先 DB
    raw = await redis_client.get(_key(run_id))
    if raw is not None:
        assert ckpt._parse_cache(raw)[0] <= 1
    assert await ckpt.load_state(redis_client, run_id, db_session) == committed


async def test_savepoint_rollback_discards_pending_publish(
    db_session: AsyncSession, redis_client
) -> None:
    run_id = uuid.uuid4()
    committed = {"phase": "art_confirm", "v": 1}
    db_session.add(RunCheckpoint(run_id=run_id, state=committed, revision=1))
    await db_session.commit()

    try:
        async with db_session.begin_nested():
            await ckpt.save_state(
                redis_client, run_id, {"phase": "art_confirm", "v": 2}, db_session
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    await db_session.commit()
    await asyncio.sleep(0)

    raw = await redis_client.get(_key(run_id))
    if raw is not None:
        assert ckpt._parse_cache(raw)[0] <= 1
    assert await ckpt.load_state(redis_client, run_id, db_session) == committed


async def test_clear_state_discards_pending_publish(db_session: AsyncSession, redis_client) -> None:
    run_id = uuid.uuid4()
    await ckpt.save_state(redis_client, run_id, {"phase": "done"}, db_session)
    await ckpt.clear_state(redis_client, run_id, db_session)
    await db_session.commit()
    await asyncio.sleep(0)

    # 同事务 save 后 clear：commit 后不得再把已删除 state 发布回 Redis
    assert await redis_client.get(_key(run_id)) is None
    assert await db_session.get(RunCheckpoint, run_id) is None


async def test_save_and_load_survive_redis_outage(db_session: AsyncSession) -> None:
    run_id = uuid.uuid4()
    dead = _DeadRedis()
    state = {"phase": "qa"}

    await ckpt.save_state(dead, run_id, state, db_session)
    await db_session.commit()
    await asyncio.sleep(0)  # 发布失败仅告警，不得影响事务
    assert (await db_session.get(RunCheckpoint, run_id)).revision == 1

    assert await ckpt.load_state(dead, run_id, db_session) == state
