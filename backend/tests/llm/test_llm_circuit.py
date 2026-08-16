"""LLM 熔断器单测（Redis）。"""

from __future__ import annotations

import uuid

import pytest
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider
from app.llm import circuit


@pytest.mark.asyncio
async def test_circuit_opens_after_threshold(redis_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_circuit_enabled", True)
    monkeypatch.setattr(settings, "llm_circuit_failure_threshold", 3)
    monkeypatch.setattr(settings, "llm_circuit_open_s", 30)

    uid = uuid.uuid4()
    key = circuit.circuit_key(uid, LLMProvider.OPENAI_COMPAT, "https://api.example.com/v1")
    await redis_client.delete(key)

    await circuit.assert_circuit_closed(redis_client, key)
    await circuit.record_failure(redis_client, key)
    await circuit.record_failure(redis_client, key)
    await circuit.assert_circuit_closed(redis_client, key)  # 未达阈值

    await circuit.record_failure(redis_client, key)
    with pytest.raises(AppError) as ei:
        await circuit.assert_circuit_closed(redis_client, key)
    assert ei.value.code == ErrorCode.LLM_CIRCUIT_OPEN


@pytest.mark.asyncio
async def test_circuit_success_resets(redis_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_circuit_enabled", True)
    monkeypatch.setattr(settings, "llm_circuit_failure_threshold", 2)
    monkeypatch.setattr(settings, "llm_circuit_open_s", 30)

    uid = uuid.uuid4()
    key = circuit.circuit_key(uid, LLMProvider.OPENAI, None)
    await redis_client.delete(key)

    await circuit.record_failure(redis_client, key)
    await circuit.record_success(redis_client, key)
    await circuit.assert_circuit_closed(redis_client, key)
    # 成功后失败计数清零，再失败一次不应打开
    await circuit.record_failure(redis_client, key)
    await circuit.assert_circuit_closed(redis_client, key)
