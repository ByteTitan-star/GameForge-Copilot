"""M1 认证全闭环：register→verify→login→refresh→logout + 错误路径。"""

import httpx

PWD = "password123"
EMAIL = "a@b.com"


async def _register(client: httpx.AsyncClient, email: str = EMAIL) -> str:
    """注册并返回 verify token（由 conftest 捕获 enqueue）。"""
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": PWD}
    )
    assert resp.status_code == 201, resp.text
    return ""  # token 从 fixture 取


async def test_register_verify_login_refresh_logout(
    client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    # 1. 注册
    resp = await _register(client)
    token = sent[f"verify:{EMAIL}"]
    assert token
    assert len(token) == 6

    # 2. 验证邮箱
    resp = await client.post(
        "/api/v1/auth/verify-email", json={"email": EMAIL, "code": token}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email_verified"] is True

    # 3. 登录（已验证）
    resp = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": PWD}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    refresh = body["refresh_token"]
    assert body["user"]["email_verified"] is True
    assert body["user"]["role"] == "user"

    # 4. refresh 轮换
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200, resp.text
    new_refresh = resp.json()["data"]["refresh_token"]
    assert new_refresh != refresh

    # 5. 旧 refresh 失效
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 401

    # 6. logout
    resp = await client.post("/api/v1/auth/logout", json={"refresh_token": new_refresh})
    assert resp.status_code == 204
    assert resp.text == ""

    # 7. logout 后 refresh 失效
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert resp.status_code == 401


async def test_register_duplicate_email_409(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "dup@b.com", "password": PWD}
    )
    assert resp.status_code == 201
    resp = await client.post(
        "/api/v1/auth/register", json={"email": "dup@b.com", "password": PWD}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_login_wrong_password_401(client: httpx.AsyncClient, sent: dict[str, str]) -> None:
    await client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PWD})
    resp = await client.post("/api/v1/auth/login", json={"email": EMAIL, "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_verify_bad_token_400(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/verify-email", json={"email": "a@b.com", "code": "000000"}
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_password_reset_flow(client: httpx.AsyncClient, sent: dict[str, str]) -> None:
    await client.post("/api/v1/auth/register", json={"email": EMAIL, "password": PWD})

    # 请求重置（防枚举：未知邮箱也恒返回 sent）
    resp = await client.post("/api/v1/auth/password/reset", json={"email": EMAIL})
    assert resp.status_code == 200
    assert resp.json()["data"]["sent"] is True
    token = sent[f"reset:{EMAIL}"]
    assert token

    # 确认重置
    resp = await client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": token, "new_password": "newpassword123"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == EMAIL

    # 用新密码登录
    resp = await client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "newpassword123"}
    )
    assert resp.status_code == 200

    # token 单次有效：再用 → 400
    resp = await client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"token": token, "new_password": "another123"},
    )
    assert resp.status_code == 400


async def test_password_reset_unknown_email_returns_sent(client: httpx.AsyncClient) -> None:
    """防枚举：不存在邮箱也返回 sent=true，且不发送邮件。"""
    resp = await client.post("/api/v1/auth/password/reset", json={"email": "ghost@b.com"})
    assert resp.status_code == 200
    assert resp.json()["data"]["sent"] is True


async def test_password_change_logged_in(auth_client: httpx.AsyncClient) -> None:
    """登录态改密：旧密码正确 → 新密码可登录；错误旧密码 → 401。"""
    bad = await auth_client.post(
        "/api/v1/auth/password/change",
        json={"old_password": "wrong-old", "new_password": "newpassword123"},
    )
    assert bad.status_code == 401

    ok = await auth_client.post(
        "/api/v1/auth/password/change",
        json={"old_password": PWD, "new_password": "newpassword123"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["changed"] is True

    login = await auth_client.post(
        "/api/v1/auth/login", json={"email": "u@b.com", "password": "newpassword123"}
    )
    assert login.status_code == 200


async def test_password_change_requires_auth(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/v1/auth/password/change",
        json={"old_password": PWD, "new_password": "newpassword123"},
    )
    assert r.status_code == 401
