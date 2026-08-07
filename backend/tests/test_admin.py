"""M8 管理后台：用户列表/禁用/角色 + 全局设置 get/update + disabled 拦截 + admin 守卫。"""

import httpx


async def test_list_users_admin_only(auth_client: httpx.AsyncClient) -> None:
    """普通用户访问 /admin/users → 403。"""
    r = await auth_client.get("/api/v1/admin/users")
    assert r.status_code == 403


async def test_list_and_patch_user(
    admin_client: httpx.AsyncClient, auth_client: httpx.AsyncClient
) -> None:
    # auth_client 已注册 u@b.com
    r = await admin_client.get("/api/v1/admin/users")
    assert r.status_code == 200
    d = r.json()
    emails = [u["email"] for u in d["data"]]
    assert "u@b.com" in emails and "admin@b.com" in emails

    # 找到 u@b.com 的 id
    target = next(u for u in d["data"] if u["email"] == "u@b.com")

    # 禁用 u@b.com
    r = await admin_client.patch(
        f"/api/v1/admin/users/{target['user_id']}", json={"disabled": True}
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["disabled"] is True

    # 被禁用用户登录 → 403
    r = await auth_client.post(
        "/api/v1/auth/login", json={"email": "u@b.com", "password": "password123"}
    )
    assert r.status_code == 403

    # 恢复
    r = await admin_client.patch(
        f"/api/v1/admin/users/{target['user_id']}", json={"disabled": False}
    )
    assert r.json()["data"]["disabled"] is False


async def test_settings_get_update(admin_client: httpx.AsyncClient) -> None:
    r = await admin_client.get("/api/v1/admin/settings")
    assert r.status_code == 200
    orig = r.json()["data"]["default_daily_token_limit"]

    r = await admin_client.put(
        "/api/v1/admin/settings",
        json={
            "default_daily_token_limit": 123456,
            "default_monthly_token_limit": 9_000_000,
            "default_rate_limit_per_min": 10,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["default_daily_token_limit"] == 123456
    assert r.json()["data"]["default_monthly_token_limit"] == 9_000_000

    # 覆盖值生效：再 GET 反映新值
    r = await admin_client.get("/api/v1/admin/settings")
    assert r.json()["data"]["default_daily_token_limit"] == 123456

    # 恢复避免影响其他测试
    await admin_client.put(
        "/api/v1/admin/settings",
        json={
            "default_daily_token_limit": orig,
            "default_monthly_token_limit": 10_000_000,
            "default_rate_limit_per_min": 30,
        },
    )


async def test_settings_admin_only(auth_client: httpx.AsyncClient) -> None:
    r = await auth_client.get("/api/v1/admin/settings")
    assert r.status_code == 403


async def test_patch_user_not_found_404(admin_client: httpx.AsyncClient) -> None:
    fake = "00000000-0000-4000-8000-000000000099"
    r = await admin_client.patch(f"/api/v1/admin/users/{fake}", json={"disabled": True})
    assert r.status_code == 404
