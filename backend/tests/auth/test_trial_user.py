"""试用账号 seed 与登录（需与前端 trial.ts 一致）。"""

import httpx
import pytest
import pytest_asyncio
from app.auth.trial import TRIAL_EMAIL, TRIAL_PASSWORD, ensure_trial_user
from app.games.official import seed_official_games
from sqlalchemy.ext.asyncio import AsyncSession


@pytest_asyncio.fixture
async def official_seeded(db_session: AsyncSession) -> None:
    await seed_official_games(db_session)


@pytest_asyncio.fixture
async def trial_client(client: httpx.AsyncClient, db_session: AsyncSession) -> httpx.AsyncClient:
    await ensure_trial_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": TRIAL_EMAIL, "password": TRIAL_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
    return client


@pytest.mark.asyncio
async def test_trial_user_login_after_seed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await ensure_trial_user(db_session)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": TRIAL_EMAIL, "password": TRIAL_PASSWORD},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["user"]["email"] == TRIAL_EMAIL
    assert body["access_token"]


@pytest.mark.asyncio
async def test_trial_user_cannot_change_password(trial_client: httpx.AsyncClient) -> None:
    resp = await trial_client.post(
        "/api/v1/auth/password/change",
        json={"old_password": TRIAL_PASSWORD, "new_password": "newpassword123"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_trial_user_cannot_patch_profile(trial_client: httpx.AsyncClient) -> None:
    resp = await trial_client.patch(
        "/api/v1/me/profile",
        json={"handle": "hacked_handle", "display_name": "Hacked"},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_trial_user_can_read_profile(trial_client: httpx.AsyncClient) -> None:
    resp = await trial_client.get("/api/v1/me/profile")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == TRIAL_EMAIL


@pytest.mark.asyncio
async def test_trial_user_cannot_favorite(trial_client: httpx.AsyncClient, official_seeded) -> None:
    meta = await trial_client.get("/api/v1/games/public/official-neon-snake")
    assert meta.status_code == 200, meta.text
    game_id = meta.json()["data"]["game_id"]
    resp = await trial_client.post(f"/api/v1/games/{game_id}/favorite")
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_trial_user_cannot_like(trial_client: httpx.AsyncClient, official_seeded) -> None:
    meta = await trial_client.get("/api/v1/games/public/official-neon-snake")
    game_id = meta.json()["data"]["game_id"]
    resp = await trial_client.post(f"/api/v1/games/{game_id}/like")
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_trial_password_reset_does_not_enqueue(
    client: httpx.AsyncClient, db_session: AsyncSession, sent: dict[str, str]
) -> None:
    await ensure_trial_user(db_session)
    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": TRIAL_EMAIL},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["sent"] is True
    assert f"reset:{TRIAL_EMAIL}" not in sent
