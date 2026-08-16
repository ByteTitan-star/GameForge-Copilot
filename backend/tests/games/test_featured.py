"""Batch C · B-C4: featured games."""

import httpx


async def test_featured_games(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> None:
    from tests.helpers_publish import publish_test_game

    gid = await publish_test_game(verified_client, admin_client)
    patch = await admin_client.patch(
        f"/api/v1/admin/games/{gid}/featured",
        json={"featured_rank": 1},
    )
    assert patch.status_code == 200, patch.text

    featured = await verified_client.get("/api/v1/games/featured")
    assert featured.status_code == 200
    assert any(g["game_id"] == str(gid) for g in featured.json()["data"])

    public = await verified_client.get("/api/v1/games/public")
    assert public.status_code == 200
    pub_row = next(g for g in public.json()["data"] if g["game_id"] == str(gid))
    assert pub_row["featured"] is True

    logs = await admin_client.get("/api/v1/admin/audit-logs")
    assert any(row["action"] == "feature_game" for row in logs.json()["data"])
