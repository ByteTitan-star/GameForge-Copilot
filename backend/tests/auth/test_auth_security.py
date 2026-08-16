"""安全原语单测：argon2、JWT、refresh rotation（fakeredis）。"""

import uuid

import fakeredis.aioredis
import jwt
import pytest
from app.auth.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)
from app.auth.tokens import issue_refresh, revoke_refresh, rotate_refresh, verify_refresh


def test_password_hash_and_verify() -> None:
    h = hash_password("password123")
    assert h != "password123"
    assert verify_password("password123", h)
    assert not verify_password("wrong", h)


def test_access_token_roundtrip() -> None:
    uid = uuid.uuid4()
    token = create_access_token(user_id=uid, role="user")
    payload = decode_access_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == "user"
    assert payload["type"] == "access"


def test_access_token_invalid_raises() -> None:
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("not-a-jwt")


async def test_refresh_issue_verify_rotate() -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    uid = uuid.uuid4()
    token = await issue_refresh(r, uid)
    assert token != generate_refresh_token()  # 两次随机不同
    assert await verify_refresh(r, token) == uid

    uid2, new_token = await rotate_refresh(r, token)
    assert uid2 == uid
    # 旧 token 失效
    assert await verify_refresh(r, token) is None
    assert await verify_refresh(r, new_token) == uid
    await r.aclose()


async def test_refresh_revoke() -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    uid = uuid.uuid4()
    token = await issue_refresh(r, uid)
    await revoke_refresh(r, token)
    assert await verify_refresh(r, token) is None
    await r.aclose()


async def test_rotate_unknown_token_returns_none() -> None:
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    assert await rotate_refresh(r, "no-such-token") is None
    await r.aclose()
