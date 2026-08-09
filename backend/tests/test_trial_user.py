"""试用账号 seed 与登录（需与前端 trial.ts 一致）。"""

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.trial import TRIAL_EMAIL, TRIAL_PASSWORD, ensure_trial_user


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
