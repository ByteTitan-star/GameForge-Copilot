"""Batch B · B-B1: template catalog + reference playtest."""

import httpx
import pytest

from app.forge.templates.loader import list_templates, reference_artifact_path
from app.sandbox.playtest import run_playtest


async def test_list_templates_returns_catalog(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/templates")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 30
    assert data[0]["template_id"] == "fruit-slash-fever"
    assert "engine" in data[0]
    assert "playable" in data[0]
    assert data[0]["playable"] is False


async def test_create_game_from_template(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.post("/api/v1/games", json={"template_id": "fruit-slash-fever"})
    assert r.status_code == 201, r.text
    gid = r.json()["data"]["game_id"]
    d = await verified_client.get(f"/api/v1/games/{gid}")
    assert d.status_code == 200
    title = d.json()["data"]["title"]
    assert "切果" in title or "水果" in title


@pytest.mark.parametrize(
    "template_id",
    [
        t["template_id"]
        for t in list_templates()
        if t.get("reference_artifact") and t.get("verified")
    ],
)
async def test_template_reference_playtest(template_id: str) -> None:
    path = reference_artifact_path(template_id)
    html = path.read_text(encoding="utf-8")
    result = await run_playtest(html)
    assert result.ok, result.errors
