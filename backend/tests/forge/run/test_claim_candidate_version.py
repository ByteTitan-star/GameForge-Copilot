"""claim_candidate_version 幂等领取。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.forge.code_candidate import claim_candidate_version


@pytest.mark.asyncio
async def test_claim_candidate_version_reuses_same_attempt(redis_client, monkeypatch) -> None:
    calls = {"n": 0}

    async def fake_next(_session, _game) -> int:
        calls["n"] += 1
        return 3 + calls["n"]

    monkeypatch.setattr("app.forge.code_candidate.next_candidate_version", fake_next)
    game = SimpleNamespace(id=uuid.uuid4(), current_version=0)
    run_id = uuid.uuid4()
    session = AsyncMock()

    v1, new1 = await claim_candidate_version(redis_client, session, game, run_id=run_id, attempt=1)
    v2, new2 = await claim_candidate_version(redis_client, session, game, run_id=run_id, attempt=1)
    assert new1 is True
    assert new2 is False
    assert v1 == v2 == 4
    assert calls["n"] == 1
