"""P4 build repair loop 与 fallback 集成测试。"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.forge.build.code_output import ParsedCodeOutput
from app.forge.build.integration import (
    format_project_repair_input,
    run_project_build_loop,
    with_design_routing,
)
from app.forge.build.pipeline import BuildPipelineResult
from app.forge.build.routing import BuildRouting
from app.forge.prompts import build_project_repair_prompt


def _project_parsed() -> ParsedCodeOutput:
    routing = BuildRouting(build="vite", renderer="canvas", dependencies=())
    return ParsedCodeOutput(
        format="project",
        files={"src/main.ts": "export {}"},
        routing=routing,
    )


def test_build_project_repair_prompt_restricts_catalog() -> None:
    prompt = build_project_repair_prompt("phaser3", ["matter-js"])
    assert "Cannot find module" in prompt
    assert "matter-js" in prompt
    assert "package.json" in prompt


def test_format_project_repair_input_includes_files() -> None:
    parsed = _project_parsed()
    msg = format_project_repair_input("base", parsed, "TS2307: cannot find foo")
    assert "base" in msg
    assert "TS2307" in msg
    assert "src/main.ts" in msg


@pytest.mark.asyncio
async def test_build_loop_success_first_attempt() -> None:
    parsed = _project_parsed()
    pipeline = MagicMock()
    pipeline.run_project = AsyncMock(
        return_value=BuildPipelineResult(ok=True, dist={"index.html": b"<html></html>"})
    )
    result = await run_project_build_loop(parsed, pipeline=pipeline, max_retries=3)
    assert result.ok
    assert result.build_attempts == 1
    assert not result.fallback_required
    pipeline.run_project.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_loop_repair_then_success() -> None:
    parsed = _project_parsed()
    pipeline = MagicMock()
    pipeline.run_project = AsyncMock(
        side_effect=[
            BuildPipelineResult(ok=False, error="build failed", logs="stderr"),
            BuildPipelineResult(ok=True, dist={"index.html": b"<html></html>"}),
        ]
    )
    repairs: list[str] = []

    async def repair_fn(current: ParsedCodeOutput, err: str) -> ParsedCodeOutput:
        repairs.append(err)
        return replace(current, files={"src/main.ts": "fixed"})

    result = await run_project_build_loop(
        parsed, pipeline=pipeline, repair_fn=repair_fn, max_retries=3
    )
    assert result.ok
    assert result.build_attempts == 2
    assert repairs == ["build failed\nstderr"]
    assert pipeline.run_project.await_count == 2


@pytest.mark.asyncio
async def test_build_loop_exhausted_requires_fallback() -> None:
    parsed = _project_parsed()
    pipeline = MagicMock()
    pipeline.run_project = AsyncMock(
        return_value=BuildPipelineResult(ok=False, error="still broken")
    )
    repair_fn = AsyncMock(return_value=parsed)
    result = await run_project_build_loop(
        parsed, pipeline=pipeline, repair_fn=repair_fn, max_retries=2
    )
    assert not result.ok
    assert result.fallback_required
    assert result.build_attempts == 2
    assert repair_fn.await_count == 1


@pytest.mark.asyncio
async def test_build_loop_validation_error_fallback() -> None:
    bad = ParsedCodeOutput(
        format="project",
        files={},
        routing=BuildRouting(build="vite"),
        errors=("project 输出缺少 files",),
    )
    result = await run_project_build_loop(bad, max_retries=3)
    assert not result.ok
    assert result.fallback_required


def test_with_design_routing_merges_deps() -> None:
    design = BuildRouting(build="vite", renderer="phaser3", dependencies=("matter-js",))
    parsed = ParsedCodeOutput(
        format="project",
        files={"src/main.ts": "x"},
        routing=BuildRouting(build="vite", renderer="canvas", dependencies=()),
    )
    merged = with_design_routing(parsed, design)
    assert merged.routing is not None
    assert merged.routing.renderer == "canvas"
    assert merged.routing.dependencies == ("matter-js",)
