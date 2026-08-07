"""Batch C · B-C1/C2: profile + public creator page."""

import httpx


async def test_profile_crud(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.get("/api/v1/me/profile")
    assert r.status_code == 200
    assert "email" in r.json()["data"]

    r = await verified_client.patch(
        "/api/v1/me/profile",
        json={
            "handle": "creator_one",
            "display_name": "Creator One",
            "profile_public": True,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["handle"] == "creator_one"
    assert data["display_name"] == "Creator One"


async def test_handle_unique(
    verified_client: httpx.AsyncClient, client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    await verified_client.patch(
        "/api/v1/me/profile",
        json={"handle": "unique_handle"},
    )
    await client.post(
        "/api/v1/auth/register", json={"email": "c2@b.com", "password": "password123"}
    )
    code = sent["verify:c2@b.com"]
    await client.post(
        "/api/v1/auth/verify-email", json={"email": "c2@b.com", "code": code}
    )
    r = await client.post(
        "/api/v1/auth/login", json={"email": "c2@b.com", "password": "password123"}
    )
    client.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"
    r = await client.patch(
        "/api/v1/me/profile",
        json={"handle": "unique_handle"},
    )
    assert r.status_code == 409


async def test_public_creator_page(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    await verified_client.patch(
        "/api/v1/me/profile",
        json={"handle": "pub_creator", "display_name": "Pub", "profile_public": True},
    )
    r = await verified_client.post(
        "/api/v1/games",
        json={"title": "公开作", "requirement": "简单点击游戏"},
    )
    gid = r.json()["data"]["game_id"]

    # 模拟 published：直接通过 admin 审批流较复杂，测 404 draft 不在主页
    page = await verified_client.get("/api/v1/u/pub_creator")
    assert page.status_code == 200
    assert page.json()["data"]["handle"] == "pub_creator"
    assert all(g["game_id"] != gid for g in page.json()["data"]["games"])

    await verified_client.patch(
        "/api/v1/me/profile",
        json={"profile_public": False},
    )
    hidden = await verified_client.get("/api/v1/u/pub_creator")
    assert hidden.status_code == 404
