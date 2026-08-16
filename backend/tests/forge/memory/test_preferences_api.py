"""P1：用户偏好 API 与存储。"""

from __future__ import annotations

import httpx
from app.models.user_preference import UserPreference
from sqlalchemy import select


async def test_preferences_crud_roundtrip(verified_client: httpx.AsyncClient) -> None:
    empty = await verified_client.get("/api/v1/me/preferences")
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["items"] == []

    put = await verified_client.put(
        "/api/v1/me/preferences",
        json={
            "category": "visual",
            "key": "style",
            "value_json": {"style": "pixel"},
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()["data"]
    assert body["category"] == "visual"
    assert body["value_json"]["style"] == "pixel"

    listed = await verified_client.get("/api/v1/me/preferences")
    assert listed.status_code == 200
    items = listed.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["key"] == "style"

    cleared = await verified_client.delete("/api/v1/me/preferences")
    assert cleared.status_code == 200
    assert cleared.json()["data"]["deleted"] == 1
    again = await verified_client.get("/api/v1/me/preferences")
    assert again.json()["data"]["items"] == []


async def test_preferences_survive_game_delete(
    verified_client: httpx.AsyncClient, db_session
) -> None:
    """ADR-02 MVP：Explicit 偏好挂在 user，删 Game 不级联删除。"""
    await verified_client.put(
        "/api/v1/me/preferences",
        json={
            "category": "visual",
            "key": "style",
            "value_json": {"style": "pixel"},
        },
    )
    game = await verified_client.post(
        "/api/v1/games", json={"title": "临时", "requirement": "测试"}
    )
    assert game.status_code == 201, game.text
    game_id = game.json()["data"]["game_id"]
    deleted = await verified_client.delete(f"/api/v1/games/{game_id}")
    assert deleted.status_code in (200, 204), deleted.text

    prefs = await db_session.scalars(select(UserPreference))
    assert len(list(prefs.all())) == 1
