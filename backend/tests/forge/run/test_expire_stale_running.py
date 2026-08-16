"""ADR-10：RUNNING 无租约超时回收。"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.core.config import settings
from app.enums import RunStatus
from app.models.game import Game
from app.models.generation_run import GenerationRun
from app.scheduler.services import expire_stale_running_runs
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_expire_stale_running_without_lease(
    verified_client: httpx.AsyncClient,
    db_session: AsyncSession,
    redis_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "running_stale_timeout_s", 60)

    game_resp = await verified_client.post(
        "/api/v1/games", json={"title": "running-stale", "requirement": "stub"}
    )
    game_id = uuid.UUID(game_resp.json()["data"]["game_id"])
    game = await db_session.get(Game, game_id)
    assert game is not None

    run_id = uuid.uuid4()
    db_session.add(
        GenerationRun(
            id=run_id,
            game_id=game_id,
            user_id=game.owner_id,
            requirement="stub",
            status=RunStatus.RUNNING.value,
            updated_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.commit()

    n = await expire_stale_running_runs(db_session, redis_client)
    assert n == 1
    run = await db_session.get(GenerationRun, run_id)
    assert run is not None and run.status == RunStatus.FAILED.value


@pytest.mark.asyncio
async def test_expire_skips_when_lease_present(
    verified_client: httpx.AsyncClient,
    db_session: AsyncSession,
    redis_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "running_stale_timeout_s", 60)

    game_resp = await verified_client.post(
        "/api/v1/games", json={"title": "running-lease", "requirement": "stub"}
    )
    game_id = uuid.UUID(game_resp.json()["data"]["game_id"])
    game = await db_session.get(Game, game_id)
    assert game is not None

    run_id = uuid.uuid4()
    db_session.add(
        GenerationRun(
            id=run_id,
            game_id=game_id,
            user_id=game.owner_id,
            requirement="stub",
            status=RunStatus.RUNNING.value,
            updated_at=datetime.now(UTC) - timedelta(hours=2),
        )
    )
    await db_session.commit()
    await redis_client.set(f"run:executing:{run_id}", "owner")

    n = await expire_stale_running_runs(db_session, redis_client)
    assert n == 0
    run = await db_session.get(GenerationRun, run_id)
    assert run is not None and run.status == RunStatus.RUNNING.value
