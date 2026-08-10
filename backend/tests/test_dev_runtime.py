"""Dev runtime debug endpoints (Redis flush, queue purge, requeue)."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.enums import RunStatus
from app.messaging.factory import get_task_publisher
from app.messaging.memory import MemoryTaskPublisher
from app.messaging.tasks import TASK_EXECUTE_RUN, run_id_payload
from app.models.generation_run import GenerationRun


@pytest.mark.asyncio
async def test_runtime_status(client: httpx.AsyncClient, redis_client) -> None:
    await redis_client.set("run:events:abc", "[]")
    await redis_client.set("usage:sys:total", "0")
    resp = await client.get("/api/v1/dev/runtime/status")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["env"] == settings.env
    assert body["redis"]["forge"] >= 1
    assert body["queue"]["backend"] == "memory"


@pytest.mark.asyncio
async def test_redis_flush_forge_scope(client: httpx.AsyncClient, redis_client) -> None:
    run_id = uuid.uuid4()
    await redis_client.set(f"run:events:{run_id}", "[]")
    await redis_client.set(f"run:ckpt:{run_id}", "{}")
    await redis_client.set("usage:sys:total", "1")

    resp = await client.post(
        "/api/v1/dev/redis/flush",
        json={"scopes": ["forge"], "run_id": str(run_id), "confirm": "FLUSH"},
    )
    assert resp.status_code == 200, resp.text
    deleted = resp.json()["data"]["deleted"]
    assert sum(deleted.values()) == 2
    assert await redis_client.get(f"run:events:{run_id}") is None
    assert await redis_client.get("usage:sys:total") == "1"


@pytest.mark.asyncio
async def test_redis_flush_all_ephemeral(client: httpx.AsyncClient, redis_client) -> None:
    await redis_client.set("run:ctrl:x", "pause")
    await redis_client.set("rl:login:127.0.0.1", "1")
    await redis_client.set("refresh:tok", "uid")

    resp = await client.post(
        "/api/v1/dev/redis/flush",
        json={"scopes": ["all_ephemeral"], "confirm": "FLUSH"},
    )
    assert resp.status_code == 200, resp.text
    assert await redis_client.get("run:ctrl:x") is None
    assert await redis_client.get("rl:login:127.0.0.1") is None
    assert await redis_client.get("refresh:tok") == "uid"


@pytest.mark.asyncio
async def test_redis_flush_requires_confirm(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/dev/redis/flush",
        json={"scopes": ["forge"], "confirm": "nope"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_queue_purge_memory(client: httpx.AsyncClient) -> None:
    run_id = uuid.uuid4()
    await get_task_publisher().publish(TASK_EXECUTE_RUN, run_id_payload(run_id))
    assert len(MemoryTaskPublisher.captured) == 1

    resp = await client.post("/api/v1/dev/queue/purge", params={"confirm": "FLUSH"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["purged"] == 1
    assert len(MemoryTaskPublisher.captured) == 0


@pytest.mark.asyncio
async def test_dev_requeue_running_with_checkpoint(
    client: httpx.AsyncClient,
    redis_client,
    db_session: AsyncSession,
    verified_client: httpx.AsyncClient,
) -> None:
    from app.models.game import Game

    game_resp = await verified_client.post(
        "/api/v1/games",
        json={"title": "requeue game", "requirement": "stub"},
    )
    game_id = uuid.UUID(game_resp.json()["data"]["game_id"])
    game = await db_session.get(Game, game_id)
    assert game is not None

    run_id = uuid.uuid4()
    run = GenerationRun(
        id=run_id,
        game_id=game_id,
        user_id=game.owner_id,
        requirement="stub",
        status=RunStatus.RUNNING.value,
    )
    db_session.add(run)
    await db_session.commit()
    await redis_client.set(
        f"run:ckpt:{run_id}",
        '{"phase":"plan_confirm","design_doc":{"title":"x"}}',
    )

    resp = await client.post(f"/api/v1/dev/runs/{run_id}/requeue")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["task"] == "resume_run"
    assert data["phase"] == "plan_confirm"


@pytest.mark.asyncio
async def test_dev_endpoints_disabled_outside_development(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "env", "production")
    resp = await client.get("/api/v1/dev/runtime/status")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_clears_active_runs_and_forge_redis(
    client: httpx.AsyncClient,
    redis_client,
    db_session: AsyncSession,
    verified_client: httpx.AsyncClient,
) -> None:
    from app.models.game import Game

    game_resp = await verified_client.post(
        "/api/v1/games", json={"title": "reset game", "requirement": "stub"}
    )
    game_id = uuid.UUID(game_resp.json()["data"]["game_id"])
    game = await db_session.get(Game, game_id)
    assert game is not None

    paused_id = uuid.uuid4()
    running_id = uuid.uuid4()
    db_session.add_all(
        [
            GenerationRun(
                id=paused_id,
                game_id=game_id,
                user_id=game.owner_id,
                requirement="stub",
                status=RunStatus.PAUSED.value,
            ),
            GenerationRun(
                id=running_id,
                game_id=game_id,
                user_id=game.owner_id,
                requirement="stub",
                status=RunStatus.RUNNING.value,
            ),
        ]
    )
    await db_session.commit()
    # forge redis 残留 + 一条排队任务
    await redis_client.set(f"run:events:{paused_id}", "[]")
    await redis_client.set(f"run:ckpt:{running_id}", "{}")
    await get_task_publisher().publish(TASK_EXECUTE_RUN, run_id_payload(paused_id))
    assert len(MemoryTaskPublisher.captured) == 1

    resp = await client.post("/api/v1/dev/reset", params={"confirm": "FLUSH"})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["failed_count"] == 2
    assert set(data["failed_runs"]) == {str(paused_id), str(running_id)}

    # active run 全部置 failed + ended_at
    for rid in (paused_id, running_id):
        row = (
            await db_session.execute(
                select(GenerationRun.status, GenerationRun.ended_at).where(
                    GenerationRun.id == rid
                )
            )
        ).one()
        assert row.status == RunStatus.FAILED.value
        assert row.ended_at is not None

    # forge redis 已清，队列已清
    assert await redis_client.get(f"run:events:{paused_id}") is None
    assert await redis_client.get(f"run:ckpt:{running_id}") is None
    assert len(MemoryTaskPublisher.captured) == 0


@pytest.mark.asyncio
async def test_reset_requires_confirm(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/dev/reset", params={"confirm": "nope"})
    assert resp.status_code == 400
