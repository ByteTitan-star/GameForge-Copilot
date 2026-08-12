import json
import uuid

import httpx
from sqlalchemy import select

from app.core import db
from app.enums import WSEventType
from app.forge import state as ckpt
from app.forge.event_log import list_events
from app.forge.events import publish_event
from app.messaging.memory import MemoryTaskPublisher
from app.messaging.outbox import dispatch_pending
from app.models.run_checkpoint import RunCheckpoint
from app.models.task_outbox import TaskOutbox


async def _make_run(client: httpx.AsyncClient) -> uuid.UUID:
    game = await client.post(
        "/api/v1/games", json={"title": "reliability", "requirement": "test"}
    )
    game_id = game.json()["data"]["game_id"]
    run = await client.post(
        f"/api/v1/games/{game_id}/runs", json={"requirement": "test"}
    )
    return uuid.UUID(run.json()["data"]["run_id"])


async def test_checkpoint_falls_back_to_database(
    verified_client: httpx.AsyncClient, redis_client
) -> None:
    run_id = await _make_run(verified_client)
    state = {"phase": "plan_confirm", "design_doc": {"title": "durable"}}
    async with db.SessionLocal() as session:
        await ckpt.save_state(redis_client, run_id, state, session)
        await session.commit()
    await redis_client.delete(f"run:ckpt:{run_id}")

    async with db.SessionLocal() as session:
        assert await ckpt.load_state(redis_client, run_id, session) == state
        assert await session.get(RunCheckpoint, run_id) is not None
    assert await redis_client.get(f"run:ckpt:{run_id}") is not None


async def test_outbox_dispatches_committed_run_task(
    verified_client: httpx.AsyncClient,
) -> None:
    run_id = await _make_run(verified_client)
    MemoryTaskPublisher.reset()

    assert await dispatch_pending() >= 1
    assert any(
        payload.get("run_id") == str(run_id)
        for _task, payload in MemoryTaskPublisher.captured
    )
    async with db.SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(TaskOutbox).where(
                        TaskOutbox.payload["run_id"].as_string() == str(run_id)
                    )
                )
            ).all()
        )
        assert rows and all(row.published_at is not None for row in rows)


async def test_outbox_publish_failure_remains_retryable(
    verified_client: httpx.AsyncClient, monkeypatch
) -> None:
    run_id = await _make_run(verified_client)

    class FailingPublisher:
        async def publish(self, _task: str, _payload: dict) -> None:
            raise ConnectionError("broker unavailable")

    monkeypatch.setattr(
        "app.messaging.outbox.get_task_publisher", lambda: FailingPublisher()
    )
    assert await dispatch_pending() == 0

    async with db.SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(TaskOutbox).where(TaskOutbox.published_at.is_(None))
                )
            ).all()
        )
        retryable = [
            row for row in rows if str(row.payload.get("run_id")) == str(run_id)
        ]
        assert retryable
        assert retryable[0].attempts == 1
        assert retryable[0].last_error == "broker unavailable"


async def test_cancel_closes_unpublished_run_task(
    verified_client: httpx.AsyncClient,
) -> None:
    run_id = await _make_run(verified_client)
    response = await verified_client.post(f"/api/v1/runs/{run_id}/cancel")
    assert response.status_code == 200

    async with db.SessionLocal() as session:
        rows = list(
            (
                await session.scalars(
                    select(TaskOutbox).where(TaskOutbox.published_at.is_not(None))
                )
            ).all()
        )
        cancelled = [
            row for row in rows if str(row.payload.get("run_id")) == str(run_id)
        ]
        assert cancelled
        assert all(row.last_error == "cancelled before dispatch" for row in cancelled)

    MemoryTaskPublisher.reset()
    await dispatch_pending()
    assert not any(
        payload.get("run_id") == str(run_id)
        for _task, payload in MemoryTaskPublisher.captured
    )


async def test_event_sequence_is_monotonic_and_filterable(
    verified_client: httpx.AsyncClient, redis_client
) -> None:
    run_id = await _make_run(verified_client)
    await publish_event(run_id, WSEventType.PHASE_START, {"phase": "plan"})
    await publish_event(run_id, WSEventType.TOOL_CALL, {"summary": "ok"})

    all_events = await list_events(redis_client, run_id)
    first_seq = int(json.loads(all_events[-2])["seq"])
    replay = await list_events(redis_client, run_id, after=first_seq)
    assert len(replay) == 1
    assert int(json.loads(replay[0])["seq"]) == first_seq + 1
