"""P0：副作用幂等键。"""

from __future__ import annotations

import uuid

import pytest
from app.forge.reliability.idempotency import (
    already_applied,
    side_effect_key,
    try_begin_side_effect,
)


def test_side_effect_key_stable() -> None:
    run_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    a = side_effect_key(run_id, "code", "exec-1", "promote")
    b = side_effect_key(run_id, "code", "exec-1", "promote")
    assert a == b
    assert a.startswith("forge:side:")


@pytest.mark.asyncio
async def test_try_begin_side_effect_only_once(redis_client) -> None:
    run_id = uuid.uuid4()
    key = side_effect_key(run_id, "code", "e1", "promote")
    assert await try_begin_side_effect(redis_client, key) is True
    assert await try_begin_side_effect(redis_client, key) is False
    assert await already_applied(redis_client, key) is True
