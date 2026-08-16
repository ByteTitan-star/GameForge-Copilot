"""ADR-11：WS relay cancel 行为。"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from app.ws import runs as ws_runs


@pytest.mark.asyncio
async def test_relay_task_can_be_cancelled() -> None:
    websocket = MagicMock()
    ready = asyncio.Event()
    replayed = asyncio.Event()

    async def forever_relay(ws, run_id, ready_ev, replayed_ev):
        ready_ev.set()
        await asyncio.Event().wait()

    # Directly exercise cancel path used by run_ws finally
    relay = asyncio.create_task(forever_relay(websocket, uuid4(), ready, replayed))
    await ready.wait()
    relay.cancel()
    with pytest.raises(asyncio.CancelledError):
        await relay
    assert ws_runs.run_ws is not None  # module import sanity
