"""B5: game templates API."""

import httpx


async def test_list_templates(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/templates")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert "template_id" in data[0]


async def test_create_game_from_template(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.post(
        "/api/v1/games", json={"template_id": "arcade-snake"}
    )
    assert r.status_code == 201, r.text
    gid = r.json()["data"]["game_id"]
    d = await verified_client.get(f"/api/v1/games/{gid}")
    assert d.status_code == 200
    assert "蛇" in d.json()["data"]["title"] or "贪吃蛇" in d.json()["data"]["title"]
