"""Batch B · B-B1: template catalog + reference playtest."""

import httpx
import pytest

from app.forge.templates.loader import list_templates, reference_artifact_path
from app.sandbox.playtest import run_playtest


async def test_list_templates_verified_only(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/templates")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 3
    assert "template_id" in data[0]


async def test_create_game_from_template(verified_client: httpx.AsyncClient) -> None:
    r = await verified_client.post(
        "/api/v1/games", json={"template_id": "arcade-snake"}
    )
    assert r.status_code == 201, r.text
    gid = r.json()["data"]["game_id"]
    d = await verified_client.get(f"/api/v1/games/{gid}")
    assert d.status_code == 200
    assert "蛇" in d.json()["data"]["title"] or "贪吃蛇" in d.json()["data"]["title"]


@pytest.mark.parametrize("template_id", [t["template_id"] for t in list_templates()])
async def test_template_reference_playtest(template_id: str) -> None:
    path = reference_artifact_path(template_id)
    html = path.read_text(encoding="utf-8")
    result = await run_playtest(html)
    assert result.ok, result.errors
