from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.forge.skills.models import LoadedSkill, ResolvedSkills
from app.forge.skills.usage import maybe_publish_skill_usage


def _resolved() -> ResolvedSkills:
    method = LoadedSkill(id="art/ink-wash", name="Ink", kind="methodology", body="x")
    policy = LoadedSkill(id="policy/conventions", name="Conv", kind="policy", body="y")
    return ResolvedSkills(policy=(policy,), methodology=(method,), loaded_body_count=2)


@pytest.mark.asyncio
async def test_publish_skill_usage_when_run_id_present() -> None:
    run_id = uuid.uuid4()
    with patch("app.forge.skills.usage.publish_event", new_callable=AsyncMock) as pub:
        await maybe_publish_skill_usage({"run_id": str(run_id)}, "art", _resolved())
    pub.assert_awaited_once()
    args = pub.await_args.args
    payload = args[2]
    assert payload["tool"] == "skill"
    assert payload["phase"] == "art"
    assert payload["summary"] == "Ink"
    assert payload["args"]["skill_ids"] == ["art/ink-wash"]
    assert payload["args"]["skill_names"] == ["Ink"]


@pytest.mark.asyncio
async def test_repair_skill_usage_maps_to_code_phase() -> None:
    run_id = uuid.uuid4()
    with patch("app.forge.skills.usage.publish_event", new_callable=AsyncMock) as pub:
        await maybe_publish_skill_usage({"run_id": str(run_id)}, "repair", _resolved())
    assert pub.await_args.args[2]["phase"] == "code"


@pytest.mark.asyncio
async def test_skip_skill_usage_without_methodology() -> None:
    run_id = uuid.uuid4()
    empty = ResolvedSkills(policy=(), methodology=(), loaded_body_count=0)
    with patch("app.forge.skills.usage.publish_event", new_callable=AsyncMock) as pub:
        await maybe_publish_skill_usage({"run_id": str(run_id)}, "art", empty)
    pub.assert_not_called()


@pytest.mark.asyncio
async def test_skip_skill_usage_without_run_id() -> None:
    with patch("app.forge.skills.usage.publish_event", new_callable=AsyncMock) as pub:
        await maybe_publish_skill_usage({}, "art", _resolved())
    pub.assert_not_called()
