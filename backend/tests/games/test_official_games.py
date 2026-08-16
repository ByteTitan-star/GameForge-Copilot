"""官方预置游戏 API（Batch A · B-A1/B-A2）。"""

import shutil
import uuid

import httpx
from app.games.official import OFFICIAL_CATALOG, seed_official_games


async def test_list_official_games(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/api/v1/official-games")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 3
    slugs = {item["slug"] for item in data}
    assert "official-neon-snake" in slugs
    assert all(item["play_url"].startswith("/play/") for item in data)


async def test_list_official_games_en_locale(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/api/v1/official-games?locale=en")
    assert r.status_code == 200
    titles = {item["title"] for item in r.json()["data"]}
    assert "Neon Snake" in titles
    assert "塔防雏形" not in titles


async def test_play_official_en_locale(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/play/official-neon-snake?lang=en")
    assert r.status_code == 200
    assert "Start game" in r.text


async def test_play_official_slug(client: httpx.AsyncClient, official_seeded) -> None:
    r = await client.get("/play/official-neon-snake")
    assert r.status_code == 200
    assert "canvas" in r.text


async def test_public_game_meta_by_slug(client: httpx.AsyncClient, official_seeded) -> None:
    """Play shell resolves metadata via GET /games/public/{slug} (no /play/{slug}/meta 404)."""
    r = await client.get("/api/v1/games/public/official-neon-snake")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["slug"] == "official-neon-snake"
    assert data["title"]
    assert "play_count" in data


async def test_fork_official_game(verified_client: httpx.AsyncClient, official_seeded) -> None:
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


async def test_fork_unknown_slug_404(verified_client: httpx.AsyncClient, official_seeded) -> None:
    r = await verified_client.post("/api/v1/games/fork/not-a-real-slug")
    assert r.status_code == 404


async def test_seed_idempotent(db_session) -> None:
    n1 = await seed_official_games(db_session)
    n2 = await seed_official_games(db_session)
    assert (n1.created, n1.refreshed) == (3, 0)
    assert (n2.created, n2.refreshed) == (0, 3)


async def test_seed_repairs_missing_artifact(db_session) -> None:
    """已存在的官方游戏产物丢失 → 重跑 seed 从源重新物化。"""
    from app.hosting.local import artifact_dir

    snake = next(s for s in OFFICIAL_CATALOG if s.slug == "official-neon-snake")
    await seed_official_games(db_session)
    target = artifact_dir(snake.game_id, 1)
    shutil.rmtree(target)
    assert not target.exists()

    n = await seed_official_games(db_session)
    assert (n.created, n.refreshed) == (0, 3)  # 行已存在，刷新产物
    assert target.exists()
    assert "canvas" in (target / "index.html").read_text(encoding="utf-8").lower()


async def test_seed_self_heals_stale_uuid(db_session) -> None:
    """历史随机 UUID 的官方行 → seed 自愈：迁移到固定 UUID + 删旧产物 + 从源重建。"""
    from app.hosting.local import artifact_dir
    from app.models.game import Game

    snake = next(s for s in OFFICIAL_CATALOG if s.slug == "official-neon-snake")
    await seed_official_games(db_session)  # 基线：固定 id 行
    stable = await db_session.get(Game, snake.game_id)
    owner_id = stable.owner_id

    # 模拟历史随机 UUID：删固定行，插随机 id 同 slug 旧行 + 旧产物
    await db_session.delete(stable)  # ON DELETE CASCADE 连带 versions
    await db_session.commit()
    stale_id = uuid.uuid4()
    db_session.add(
        Game(
            id=stale_id,
            owner_id=owner_id,
            slug=snake.slug,
            title="旧",
            requirement="旧",
            status="published",
            current_version=1,
        )
    )
    await db_session.commit()
    stale_dir = artifact_dir(stale_id, 1)
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "index.html").write_text("stale", encoding="utf-8")

    n = await seed_official_games(db_session)
    assert (n.created, n.refreshed) == (1, 2)  # snake 自愈重建，另两刷新
    assert await db_session.get(Game, snake.game_id) is not None
    assert await db_session.get(Game, stale_id) is None  # 旧行已删
    assert not stale_dir.exists()  # 旧产物已清
    healed = (artifact_dir(snake.game_id, 1) / "index.html").read_text(encoding="utf-8")
    assert "stale" not in healed
    assert "canvas" in healed.lower()  # 从源重写，非旧内容
