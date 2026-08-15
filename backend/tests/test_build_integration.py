"""build integration 入口测试。"""

import json

import pytest

from app.forge.build.integration import parse_llm_code_output, run_project_pipeline


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
