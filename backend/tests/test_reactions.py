"""Batch C · B-C3: like / favorite + reactions 态读取。"""

import uuid

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


async def test_get_reaction_state_reflects_toggle(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    from tests.helpers_publish import publish_test_game

    gid = await publish_test_game(verified_client, admin_client)

    r = await verified_client.get(f"/api/v1/games/{gid}/reactions")
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {
        "game_id": str(gid),
        "liked": False,
        "favorited": False,
        "like_count": 0,
        "favorite_count": 0,
    }

    await verified_client.post(f"/api/v1/games/{gid}/like")
    r = await verified_client.get(f"/api/v1/games/{gid}/reactions")
    assert r.json()["data"]["liked"] is True
    assert r.json()["data"]["like_count"] == 1


async def test_get_reaction_state_unknown_game_404(
    verified_client: httpx.AsyncClient,
) -> None:
    r = await verified_client.get(f"/api/v1/games/{uuid.uuid4()}/reactions")
    assert r.status_code == 404


async def test_unlike_via_delete(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    from tests.helpers_publish import publish_test_game

    gid = await publish_test_game(verified_client, admin_client)
    await verified_client.post(f"/api/v1/games/{gid}/like")

    dele = await verified_client.delete(f"/api/v1/games/{gid}/like")
    assert dele.status_code == 200, dele.text
    assert dele.json()["data"]["active"] is False
    assert dele.json()["data"]["like_count"] == 0

    r = await verified_client.get(f"/api/v1/games/{gid}/reactions")
    assert r.json()["data"]["liked"] is False


async def test_delete_like_idempotent(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    from tests.helpers_publish import publish_test_game

    gid = await publish_test_game(verified_client, admin_client)
    # 未点赞直接 DELETE：noop，200，计数仍为 0
    r = await verified_client.delete(f"/api/v1/games/{gid}/like")
    assert r.status_code == 200
    assert r.json()["data"]["like_count"] == 0
