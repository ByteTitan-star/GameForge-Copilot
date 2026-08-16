"""ADR-07 P1-18: OAuth email bind requires verified account."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.auth import oauth as oauth_mod
from app.core.errors import AppError, ErrorCode


@pytest.mark.asyncio
async def test_oauth_callback_rejects_unverified_existing_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = SimpleNamespace(
        id=uuid4(), email="victim@example.com", email_verified=False
    )
    profile = SimpleNamespace(email="victim@example.com", provider_sub="gh-1")

    db = AsyncMock()
    r = AsyncMock()
    r.getdel = AsyncMock(return_value="github")

    call_n = {"n": 0}

    async def _scalar(_stmt):  # noqa: ANN001
        call_n["n"] += 1
        # 1st: OAuthAccount lookup → None; 2nd: User by email → existing
        if call_n["n"] == 1:
            return None
        return existing

    db.scalar = AsyncMock(side_effect=_scalar)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    monkeypatch.setattr(
        oauth_mod, "fetch_oauth_profile", AsyncMock(return_value=profile)
    )

    with pytest.raises(AppError) as ei:
        await oauth_mod.oauth_callback(db, r, "github", "code", "state")
    assert ei.value.code == ErrorCode.EMAIL_NOT_VERIFIED
    db.add.assert_not_called()
