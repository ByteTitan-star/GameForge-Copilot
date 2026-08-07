"""Batch C · publish helper for social tests."""

import uuid

import httpx
from sqlalchemy import select

from app.core import db
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion

_HTML = "<html><body><canvas></canvas><button>go</button><script></script></body></html>"


async def publish_test_game(
    verified_client: httpx.AsyncClient, admin_client: httpx.AsyncClient
) -> uuid.UUID:
    r = await verified_client.post(
        "/api/v1/games",
        json={"title": "社交测", "requirement": "点击得分"},
    )
    gid = uuid.UUID(r.json()["data"]["game_id"])
    await store.write_artifact(gid, 1, {"index.html": _HTML})
    async with db.SessionLocal() as s:
        game = await s.scalar(select(Game).where(Game.id == gid))
        assert game is not None
        game.current_version = 1
        s.add(
            GameVersion(
                game_id=gid,
                version=1,
                artifact_path=f"{gid}/1/index.html",
                design_doc={"title": "社交测", "gameplay": "点击得分"},
            )
        )
        await s.commit()
    submit = await verified_client.post(
        f"/api/v1/games/{gid}/publish/submit", json={"version": 1}
    )
    pr_id = submit.json()["data"]["publish_request_id"]
    await admin_client.post(f"/api/v1/publish/{pr_id}/approve")
    return gid
