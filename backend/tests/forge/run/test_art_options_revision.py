"""ensure_art_options_revision：新行 + 旧行 STALE。"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core import db as db_module
from app.enums import ArtifactKind, ArtifactStatus
from app.forge.lineage import ensure_art_options_revision
from app.models.artifact_revision import ArtifactRevision


@pytest.mark.asyncio
async def test_art_options_revision_supersedes(verified_client: httpx.AsyncClient) -> None:
    gid = uuid.UUID(
        (
            await verified_client.post(
                "/api/v1/games", json={"title": "art opts", "requirement": "r"}
            )
        ).json()["data"]["game_id"]
    )
    rid = uuid.UUID(
        (await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "x"})).json()[
            "data"
        ]["run_id"]
    )

    async with db_module.SessionLocal() as s:
        first, _ = await ensure_art_options_revision(
            s, rid, {"options": [{"id": "A"}, {"id": "B"}]}, plan_revision_id=None
        )
        second, changed = await ensure_art_options_revision(
            s,
            rid,
            {"options": [{"id": "A", "name": "x"}, {"id": "B", "name": "y"}]},
            plan_revision_id=None,
        )
        await s.commit()
        first_id, second_id = first.id, second.id

    assert changed is True
    assert second_id != first_id

    async with db_module.SessionLocal() as s:
        old = await s.get(ArtifactRevision, first_id)
        assert old is not None
        assert old.status == ArtifactStatus.STALE.value
        assert old.supersedes is None
        new = await s.get(ArtifactRevision, second_id)
        assert new is not None
        assert new.supersedes == first_id
        rows = list(
            (
                await s.scalars(
                    select(ArtifactRevision).where(
                        ArtifactRevision.run_id == rid,
                        ArtifactRevision.kind == ArtifactKind.ART_OPTIONS.value,
                    )
                )
            ).all()
        )
        assert len(rows) == 2
