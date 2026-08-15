"""graph 与构建链的集成入口，避免 graph.py 直接堆构建细节。"""

from __future__ import annotations

from app.forge.build.code_output import ParsedCodeOutput, parse_code_output
from app.forge.build.pipeline import BuildPipeline, BuildPipelineResult


def parse_llm_code_output(raw: str, *, engine_id: str) -> ParsedCodeOutput:
    return parse_code_output(raw, default_engine=engine_id)


async def run_project_pipeline(
    parsed: ParsedCodeOutput,
) -> BuildPipelineResult | None:
    if parsed.format != "project" or parsed.routing is None or parsed.errors:
        return None
    return await BuildPipeline().run_project(parsed.files, parsed.routing)
