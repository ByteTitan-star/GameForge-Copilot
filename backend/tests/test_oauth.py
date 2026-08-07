"""B7: OAuth mock tests."""

import httpx
import pytest

from app.auth.oauth import OAuthProfile


@pytest.fixture
def _oauth_config(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "oauth_github_client_id", "test-id")
    monkeypatch.setattr(settings, "oauth_github_client_secret", "test-secret")


async def test_oauth_start_github(
    client: httpx.AsyncClient, redis_client, _oauth_config
) -> None:
    r = await client.get("/api/v1/auth/oauth/github/start")
    assert r.status_code == 200, r.text
    assert "github.com" in r.json()["data"]["redirect_url"]


async def test_oauth_callback_mock_profile(
    client: httpx.AsyncClient,
    redis_client,
    _oauth_config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.auth import oauth as oauth_mod

    async def _fake(_provider: str, _code: str) -> OAuthProfile:
        return OAuthProfile(provider_sub="999", email="oauth@b.com", name="oauth")

    monkeypatch.setattr(oauth_mod, "fetch_oauth_profile", _fake)
    start = await client.get("/api/v1/auth/oauth/github/start")
    state = start.json()["data"]["state"]
    r = await client.get(
        f"/api/v1/auth/oauth/github/callback?code=fake&state={state}"
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["access_token"]
    assert r.json()["data"]["user"]["email"] == "oauth@b.com"
