"""HIL / 用户暂停等待超时：过期 PAUSED run 自动 FAILED。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.config import settings
from app.enums import RunStatus
from app.models.game import Game
from app.models.generation_run import GenerationRun
from app.scheduler.services import expire_stale_paused_runs
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_expire_stale_paused_runs(
    verified_client: httpx.AsyncClient,
    db_session: AsyncSession,
    redis_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "hil_wait_timeout_s", 60)

    game_resp = await verified_client.post(
        "/api/v1/games", json={"title": "hil-timeout", "requirement": "stub"}
    )
    game_id = uuid.UUID(game_resp.json()["data"]["game_id"])
    game = await db_session.get(Game, game_id)
    assert game is not None

    stale_id = uuid.uuid4()
    fresh_id = uuid.uuid4()
    old = datetime.now(UTC) - timedelta(hours=2)
    recent = datetime.now(UTC)
    db_session.add_all(
        [
            GenerationRun(
                id=stale_id,
                game_id=game_id,
                user_id=game.owner_id,
                requirement="stub",
                status=RunStatus.PAUSED.value,
                updated_at=old,
            ),
            GenerationRun(
                id=fresh_id,
                game_id=game_id,
                user_id=game.owner_id,
                requirement="stub",
                status=RunStatus.PAUSED.value,
                updated_at=recent,
            ),
        ]
    )
    await db_session.commit()

    n = await expire_stale_paused_runs(db_session, redis_client)
    assert n == 1

    stale = await db_session.get(GenerationRun, stale_id)
    fresh = await db_session.get(GenerationRun, fresh_id)
    assert stale is not None and stale.status == RunStatus.FAILED.value
    assert stale.ended_at is not None
    assert fresh is not None and fresh.status == RunStatus.PAUSED.value
