"""M3 用量：record_usage → /me/usage 读取 + /admin/usage + 权限。"""

import uuid

import fakeredis.aioredis
import httpx

from app.usage.store import record_usage


async def test_me_usage_empty(auth_client: httpx.AsyncClient) -> None:
    r = await auth_client.get("/api/v1/me/usage")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["today"] == {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    assert d["total"]["calls"] == 0
    quota = d["quota"]
    assert quota["daily_token_limit"] == 500_000
    assert quota["daily_used"] == 0
    assert quota["remaining"] == 500_000


async def test_me_usage_after_record(
    auth_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    me_user_id: uuid.UUID,
) -> None:
    await record_usage(redis_client, me_user_id, input_tokens=1000, output_tokens=200)
    await record_usage(redis_client, me_user_id, input_tokens=50, output_tokens=10)

    r = await auth_client.get("/api/v1/me/usage")
    assert r.status_code == 200
    d = r.json()["data"]
    today = d["today"]
    assert today["input_tokens"] == 1050
    assert today["output_tokens"] == 210
    assert today["calls"] == 2
    assert d["total"]["input_tokens"] == 1050
    assert d["quota"]["daily_used"] == 1260
    assert d["quota"]["remaining"] == 500_000 - 1260


async def test_me_usage_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/me/usage")
    assert r.status_code == 401


async def test_admin_usage_forbidden_for_user(auth_client: httpx.AsyncClient) -> None:
    r = await auth_client.get("/api/v1/admin/usage")
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"


async def test_admin_usage_after_record(
    admin_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    me_user_id: uuid.UUID,
) -> None:
    """admin 看系统总量 + top_users（含 u@b.com）。me_user_id 来自 auth_client 的注册，
    但 admin_client 用独立 client——这里仅 seed Redis（共享 fake）+ DB（共享 engine）。"""
    await record_usage(redis_client, me_user_id, input_tokens=300, output_tokens=100)

    r = await admin_client.get("/api/v1/admin/usage")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    sys_today = d["system"]["today"]
    assert sys_today["input_tokens"] == 300
    assert sys_today["output_tokens"] == 100
    assert sys_today["calls"] == 1

    top = d["top_users"]
    assert len(top) == 1
    assert top[0]["email"] == "u@b.com"
    assert top[0]["month_input_tokens"] == 300
    assert top[0]["month_output_tokens"] == 100
    assert top[0]["calls"] == 1


async def test_admin_usage_empty(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/usage")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["system"]["today"]["calls"] == 0
    assert d["top_users"] == []


async def test_admin_usage_unauth_401(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/admin/usage")
    assert r.status_code == 401
