"""Shared httpx client pooling (#147 P1)."""

from __future__ import annotations

import pytest

from app.core import http_client


@pytest.fixture(autouse=True)
async def _reset_client() -> None:
    await http_client.aclose_http_client()
    yield
    await http_client.aclose_http_client()


def test_get_http_client_reuses_singleton() -> None:
    a = http_client.get_http_client()
    b = http_client.get_http_client()
    assert a is b
    assert a.trust_env is False


@pytest.mark.asyncio
async def test_aclose_allows_fresh_client() -> None:
    first = http_client.get_http_client()
    await http_client.aclose_http_client()
    second = http_client.get_http_client()
    assert first is not second
