"""graph 与构建链的集成入口，避免 graph.py 直接堆构建细节。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.core.config import settings
from app.forge.build.code_output import ParsedCodeOutput, parse_code_output
from app.forge.build.pipeline import BuildPipeline, BuildPipelineResult
from app.forge.build.routing import BuildRouting


def parse_llm_code_output(raw: str, *, engine_id: str) -> ParsedCodeOutput:
    return parse_code_output(raw, default_engine=engine_id)


async def load_stored_project_source(
    game_id: uuid.UUID, version: int
) -> dict[str, str]:
    """从已落盘的 source/ 层加载工程源码（QA 重试 vite 修复基线）。"""
    from app.hosting import store

    files: dict[str, str] = {}
    for meta in await store.list_files(game_id, version):
        if not meta.path.startswith("source/"):
            continue
        rel = meta.path.removeprefix("source/")
        if not rel:
            continue
        data = await store.read_bytes(game_id, version, meta.path)
        if data is not None:
            files[rel] = data.decode("utf-8", errors="replace")
    return files


async def run_project_pipeline(
    parsed: ParsedCodeOutput,
) -> BuildPipelineResult | None:
    if parsed.format != "project" or parsed.routing is None or parsed.errors:
        return None
    return await BuildPipeline().run_project(parsed.files, parsed.routing)


RepairFn = Callable[[ParsedCodeOutput, str], Awaitable[ParsedCodeOutput]]


@dataclass
class ProjectBuildLoopResult:
    ok: bool
    pipeline_result: BuildPipelineResult | None = None
    final_parsed: ParsedCodeOutput | None = None
    build_attempts: int = 0
    fallback_required: bool = False


def format_project_repair_input(
    base_user_msg: str,
    parsed: ParsedCodeOutput,
    build_error: str,
) -> str:
    """拼装 project Repair Agent 用户消息（§15-16）。"""
    routing = parsed.routing.to_dict() if parsed.routing else {}
    payload = {
        "format": "project",
        **routing,
        "files": parsed.files,
    }
    return "\n\n".join(
        [
            base_user_msg,
            f"【构建错误 stderr/日志】\n{build_error[:12000]}",
            "【当前工程源码 JSON（仅可修改 files / dependencies）】\n"
            + json.dumps(payload, ensure_ascii=False, indent=2),
        ]
    )


async def run_project_build_loop(
    initial: ParsedCodeOutput,
    *,
    repair_fn: RepairFn | None = None,
    max_retries: int | None = None,
    pipeline: BuildPipeline | None = None,
) -> ProjectBuildLoopResult:
    """Vite 构建失败 → Repair → 重建，最多 build_max_retries 次（§16）。"""
    limit = max_retries if max_retries is not None else settings.build_max_retries
    builder = pipeline or BuildPipeline()
    current = initial
    last_result: BuildPipelineResult | None = None

    for attempt in range(1, limit + 1):
        if current.format != "project" or current.routing is None or current.errors:
            return ProjectBuildLoopResult(
                ok=False,
                final_parsed=current,
                build_attempts=attempt,
                fallback_required=True,
            )

        last_result = await builder.run_project(current.files, current.routing)
        if last_result.ok:
            return ProjectBuildLoopResult(
                ok=True,
                pipeline_result=last_result,
                final_parsed=current,
                build_attempts=attempt,
            )

        build_error = (last_result.error or "") + "\n" + (last_result.logs or "")
        if attempt >= limit or repair_fn is None:
            break

        current = await repair_fn(current, build_error.strip())

    return ProjectBuildLoopResult(
        ok=False,
        pipeline_result=last_result,
        final_parsed=current,
        build_attempts=limit,
        fallback_required=True,
    )


def merge_routing(
    design_routing: BuildRouting, parsed: ParsedCodeOutput
) -> BuildRouting:
    """design_doc routing 为基线，LLM project JSON 可覆盖 dependencies 等。"""
    if parsed.routing is None:
        return design_routing
    return BuildRouting(
        build=design_routing.build if design_routing.build == "vite" else parsed.routing.build,
        renderer=parsed.routing.renderer or design_routing.renderer,
        ui=parsed.routing.ui or design_routing.ui,
        dependencies=parsed.routing.dependencies or design_routing.dependencies,
    )


def with_design_routing(
    parsed: ParsedCodeOutput, design_routing: BuildRouting
) -> ParsedCodeOutput:
    if parsed.routing is None:
        return parsed
    return ParsedCodeOutput(
        format=parsed.format,
        files=parsed.files,
        routing=merge_routing(design_routing, parsed),
        errors=parsed.errors,
    )
