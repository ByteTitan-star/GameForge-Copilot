"""偏好 API（ADR-16 v2）：目录键形态 + 归档语义。"""

from __future__ import annotations

import httpx


async def test_preferences_crud_roundtrip(verified_client: httpx.AsyncClient) -> None:
    empty = await verified_client.get("/api/v1/me/preferences")
    assert empty.status_code == 200, empty.text
    assert empty.json()["data"]["items"] == []

    put = await verified_client.put(
        "/api/v1/me/preferences",
        json={"preference_key": "theme", "value": "pixel"},  # 别名 → visual.style
    )
    assert put.status_code == 200, put.text
    body = put.json()["data"]
    assert body["preference_key"] == "visual.style"  # 归一后落库
    assert body["value"] == "pixel" and body["source"] == "explicit"

    listed = await verified_client.get("/api/v1/me/preferences")
    items = listed.json()["data"]["items"]
    assert [i["preference_key"] for i in items] == ["visual.style"]

    # 单键删除 = 归档
    removed = await verified_client.delete("/api/v1/me/preferences/visual.style")
    assert removed.status_code == 200
    assert removed.json()["data"]["archived"] == 1
    again = await verified_client.get("/api/v1/me/preferences")
    assert again.json()["data"]["items"] == []


async def test_preferences_reject_unknown_key_and_bad_value(
    verified_client: httpx.AsyncClient,
) -> None:
    unknown = await verified_client.put(
        "/api/v1/me/preferences",
        json={"preference_key": "random.schema_key", "value": "x"},
    )
    assert unknown.status_code == 400, unknown.text

    bad_value = await verified_client.put(
        "/api/v1/me/preferences",
        json={"preference_key": "visual.style", "value": "watercolor"},
    )
    assert bad_value.status_code == 400, bad_value.text


async def test_clear_all_archives_not_deletes(verified_client: httpx.AsyncClient) -> None:
    await verified_client.put(
        "/api/v1/me/preferences", json={"preference_key": "visual.style", "value": "pixel"}
    )
    await verified_client.put(
        "/api/v1/me/preferences", json={"preference_key": "gameplay.genre", "value": "puzzle"}
    )
    cleared = await verified_client.delete("/api/v1/me/preferences")
    assert cleared.status_code == 200
    assert cleared.json()["data"]["archived"] == 2
    assert (await verified_client.get("/api/v1/me/preferences")).json()["data"]["items"] == []
