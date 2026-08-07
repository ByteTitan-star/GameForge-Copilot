"""Batch C · B-C3: like / favorite."""

import httpx


async def test_like_and_favorite(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    from tests.helpers_publish import publish_test_game

    gid = await publish_test_game(verified_client, admin_client)
    like = await verified_client.post(f"/api/v1/games/{gid}/like")
    assert like.status_code == 200, like.text
    assert like.json()["data"]["active"] is True
    assert like.json()["data"]["like_count"] == 1

    unlike = await verified_client.post(f"/api/v1/games/{gid}/like")
    assert unlike.json()["data"]["active"] is False
    assert unlike.json()["data"]["like_count"] == 0

    fav = await verified_client.post(f"/api/v1/games/{gid}/favorite")
    assert fav.json()["data"]["active"] is True

    listing = await verified_client.get("/api/v1/me/favorites")
    assert listing.status_code == 200
    assert any(g["game_id"] == str(gid) for g in listing.json()["data"])
