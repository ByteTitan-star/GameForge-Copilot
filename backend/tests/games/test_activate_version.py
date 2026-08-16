"""版本 activate（Batch A · B-A6）。"""

import uuid

import httpx
from sqlalchemy import select

from app.games import services
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.user import User


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post(
        "/api/v1/games", json={"title": "版本测试", "requirement": "测试 activate"}
    )
    return uuid.UUID(r.json()["data"]["game_id"])


async def test_activate_version_api(verified_client: httpx.AsyncClient, db_session) -> None:
    gid = await _make_game(verified_client)
    user = await db_session.scalar(select(User).where(User.email_verified.is_(True)))
    assert user is not None
    game = await db_session.get(Game, gid)
    assert game is not None
    game.current_version = 2
    db_session.add(
        GameVersion(
            game_id=gid,
            version=1,
            artifact_path=f"{gid}/1/index.html",
            design_doc={"gameplay": "v1 design"},
        )
    )
    db_session.add(
        GameVersion(
            game_id=gid,
            version=2,
            artifact_path=f"{gid}/2/index.html",
            design_doc={"gameplay": "v2 design"},
        )
    )
    await db_session.commit()

    r = await verified_client.post(f"/api/v1/games/{gid}/versions/1/activate")
    assert r.status_code == 200
    assert r.json()["data"]["current_version"] == 1

    db_session.expire_all()
    updated = await db_session.get(Game, gid)
    assert updated is not None
    assert updated.requirement == "v1 design"


async def test_activate_version_service(verified_client: httpx.AsyncClient, db_session) -> None:
    gid = await _make_game(verified_client)
    user = await db_session.scalar(select(User).where(User.email_verified.is_(True)))
    assert user is not None
    db_session.add(
        GameVersion(
            game_id=gid,
            version=1,
            artifact_path=f"{gid}/1/index.html",
            design_doc={"gameplay": "from v1"},
        )
    )
    game = await db_session.get(Game, gid)
    assert game is not None
    game.current_version = 1
    await db_session.commit()

    g = await services.activate_version(db_session, user, gid, 1)
    assert g.current_version == 1
