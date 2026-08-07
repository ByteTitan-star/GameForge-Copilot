"""官方预置游戏 API（Batch A · B-A1/B-A2）。"""

import httpx
import pytest

from app.games.official import seed_official_games


@pytest.fixture
async def official_seeded(db_session) -> None:
    await seed_official_games(db_session)


async def test_list_official_games(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/api/v1/official-games")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 3
    slugs = {item["slug"] for item in data}
    assert "official-neon-snake" in slugs
    assert all(item["play_url"].startswith("/play/") for item in data)


async def test_play_official_slug(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/play/official-neon-snake")
    assert r.status_code == 200
    assert "canvas" in r.text


async def test_fork_official_game(
    verified_client: httpx.AsyncClient, official_seeded
) -> None:
    r = await verified_client.post("/api/v1/games/fork/official-neon-snake")
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["status"] == "draft"
    assert d["current_version"] == 1
    assert "副本" in d["title"]

    gid = d["game_id"]
    r = await verified_client.get(f"/draft/{gid}/1")
    assert r.status_code == 200
    assert "canvas" in r.text


async def test_fork_unknown_slug_404(
    verified_client: httpx.AsyncClient, official_seeded
) -> None:
    r = await verified_client.post("/api/v1/games/fork/not-a-real-slug")
    assert r.status_code == 404


async def test_seed_idempotent(db_session) -> None:
    n1 = await seed_official_games(db_session)
    n2 = await seed_official_games(db_session)
    assert n1 == 3
    assert n2 == 0
