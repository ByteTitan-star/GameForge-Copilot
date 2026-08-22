"""hydrate：瘦 checkpoint 恢复后能补回 design_doc。"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.forge.checkpoint_slim import hydrate_checkpoint_payloads


@pytest.mark.asyncio
async def test_hydrate_fills_design_doc_from_plan_revision() -> None:
    plan_id = uuid.uuid4()
    payload = {"title": "塔防", "gameplay": "waves"}
    row = SimpleNamespace(payload=payload)
    db = AsyncMock()
    db.get = AsyncMock(return_value=row)

    out = await hydrate_checkpoint_payloads(
        db,
        {
            "phase": "plan_confirm",
            "active_plan_revision_id": str(plan_id),
        },
    )
    assert out["design_doc"] == payload
    db.get.assert_awaited()


@pytest.mark.asyncio
async def test_hydrate_fills_art_options_from_revision() -> None:
    opts_id = uuid.uuid4()
    payload = {"options": [{"id": "A"}, {"id": "B"}]}
    row = SimpleNamespace(payload=payload)
    db = AsyncMock()
    db.get = AsyncMock(return_value=row)

    out = await hydrate_checkpoint_payloads(
        db,
        {"active_art_options_revision_id": str(opts_id)},
    )
    assert out["art_options"] == payload
