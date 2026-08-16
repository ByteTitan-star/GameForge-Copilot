"""ADR-10：promote 两段式副作用幂等。"""

from __future__ import annotations

from app.forge.reliability.idempotency import (
    commit_side_effect,
    side_effect_status,
    try_begin_side_effect,
)


async def test_pending_allows_replay_until_commit(redis_client) -> None:
    key = "forge:side:test:promote"
    assert await try_begin_side_effect(redis_client, key, value="pending") is True
    assert await side_effect_status(redis_client, key) == "pending"
    assert await try_begin_side_effect(redis_client, key, value="pending") is False
    assert await side_effect_status(redis_client, key) == "pending"
    await commit_side_effect(redis_client, key)
    assert await side_effect_status(redis_client, key) == "done"


async def test_done_status_stable(redis_client) -> None:
    key = "forge:side:test:promote2"
    await try_begin_side_effect(redis_client, key, value="pending")
    await commit_side_effect(redis_client, key)
    assert await try_begin_side_effect(redis_client, key, value="pending") is False
    assert await side_effect_status(redis_client, key) == "done"
