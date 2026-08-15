"""preview token mint/validate 测试。"""

import uuid

import pytest

from app.hosting import preview_token


@pytest.mark.asyncio
async def test_mint_and_validate(redis_client) -> None:
    gid = uuid.uuid4()
    owner = uuid.uuid4()
    token = await preview_token.mint_preview_token(
        redis_client, game_id=gid, version=2, owner_id=owner
    )
    assert token
    assert await preview_token.validate_preview_token(
        redis_client, token, game_id=gid, version=2
    )
    assert not await preview_token.validate_preview_token(
        redis_client, token, game_id=gid, version=3
    )
    assert not await preview_token.validate_preview_token(
        redis_client, "bad-token", game_id=gid, version=2
    )


def test_preview_url_path_has_trailing_slash() -> None:
    gid = uuid.uuid4()
    url = preview_token.preview_url_path("tok", gid, 1)
    assert url.endswith("/")
    assert "/preview/tok/" in url
