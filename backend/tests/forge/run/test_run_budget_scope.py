"""Run 级 token 预算触发后应可识别为 forge_run scope。"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import AppError, ErrorCode
from app.usage.store import assert_run_token_budget, record_usage


def is_forge_run_budget_error(exc: BaseException) -> bool:
    from app.forge.run_budget import is_forge_run_budget_error as _impl

    return _impl(exc)


@pytest.mark.asyncio
async def test_budget_error_has_forge_run_scope(redis_client) -> None:
    run_id = uuid.uuid4()
    user_id = uuid.uuid4()
    await record_usage(redis_client, user_id, input_tokens=50, output_tokens=50, run_id=run_id)
    with pytest.raises(AppError) as ei:
        await assert_run_token_budget(redis_client, run_id, limit=50)
    assert is_forge_run_budget_error(ei.value)
    assert ei.value.code == ErrorCode.QUOTA_EXCEEDED
