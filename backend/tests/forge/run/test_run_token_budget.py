"""单次 Forge Run token 预算熔断。"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import AppError, ErrorCode
from app.usage.store import assert_run_token_budget, record_usage, run_tokens_used


@pytest.mark.asyncio
async def test_run_tokens_used_sums_input_and_output(redis_client) -> None:
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await record_usage(
        redis_client,
        user_id,
        input_tokens=100,
        output_tokens=50,
        run_id=run_id,
    )
    assert await run_tokens_used(redis_client, run_id) == 150


@pytest.mark.asyncio
async def test_assert_run_token_budget_passes_under_limit(redis_client) -> None:
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await record_usage(
        redis_client,
        user_id,
        input_tokens=10,
        output_tokens=5,
        run_id=run_id,
    )
    await assert_run_token_budget(redis_client, run_id, limit=100)


@pytest.mark.asyncio
async def test_assert_run_token_budget_raises_when_exceeded(redis_client) -> None:
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await record_usage(
        redis_client,
        user_id,
        input_tokens=80,
        output_tokens=30,
        run_id=run_id,
    )
    with pytest.raises(AppError) as ei:
        await assert_run_token_budget(redis_client, run_id, limit=100)
    assert ei.value.code == ErrorCode.QUOTA_EXCEEDED
    assert ei.value.detail is not None
    assert ei.value.detail["used"] == 110
    assert ei.value.detail["limit"] == 100


@pytest.mark.asyncio
async def test_assert_run_token_budget_disabled_when_limit_non_positive(
    redis_client,
) -> None:
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await record_usage(
        redis_client,
        user_id,
        input_tokens=9999,
        output_tokens=9999,
        run_id=run_id,
    )
    await assert_run_token_budget(redis_client, run_id, limit=0)
    await assert_run_token_budget(redis_client, run_id, limit=-1)
