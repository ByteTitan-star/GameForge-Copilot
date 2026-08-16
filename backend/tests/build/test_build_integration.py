"""build integration 入口测试。"""

import json
import uuid

import pytest

from app.forge.build.integration import (
    load_stored_project_source,
    parse_llm_code_output,
    run_project_pipeline,
)
from app.hosting import store


def test_parse_llm_code_output_project() -> None:
    raw = json.dumps(
        {
            "format": "project",
            "build": "vite",
            "renderer": "canvas",
            "ui": "none",
            "dependencies": [],
            "files": {"src/main.ts": "export {}"},
        }
    )
    parsed = parse_llm_code_output(raw, engine_id="canvas")
    assert parsed.format == "project"
    assert parsed.errors == ()


@pytest.mark.asyncio
async def test_run_project_pipeline_returns_none_for_html() -> None:
    parsed = parse_llm_code_output("<!DOCTYPE html><html></html>", engine_id="canvas")
    assert await run_project_pipeline(parsed) is None


@pytest.mark.asyncio
async def test_load_stored_project_source(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.hosting_root", str(tmp_path))
    gid = uuid.uuid4()
    await store.write_version_layers(
        gid,
        1,
        source={"src/main.ts": b"export {}"},
        build_snapshot={"package.json": b"{}"},
        dist={"index.html": b"<html></html>"},
    )
    files = await load_stored_project_source(gid, 1)
    assert files == {"src/main.ts": "export {}"}
