"""record_usage 幂等：相同 idempotency_key 不重复累加。"""

from __future__ import annotations

import uuid

import pytest
from app.usage.store import get_user_usage, record_usage


@pytest.mark.asyncio
async def test_record_usage_idempotent_key_skips_duplicate(redis_client) -> None:
    user_id = uuid.uuid4()
    key = f"forge:side:{user_id}:plan:call-1:usage"
    await record_usage(
        redis_client,
        user_id,
        input_tokens=10,
        output_tokens=5,
        idempotency_key=key,
    )
    await record_usage(
        redis_client,
        user_id,
        input_tokens=10,
        output_tokens=5,
        idempotency_key=key,
    )
    usage = await get_user_usage(redis_client, user_id, daily_limit=1_000_000)
    assert usage.today.input_tokens == 10
    assert usage.today.output_tokens == 5
    assert usage.today.calls == 1
