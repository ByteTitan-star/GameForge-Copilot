"""CodeQaLoop 节点执行体：generate/repair、playtest、diagnose（无 run.status 副作用）。"""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.enums import RunPhase, RunStatus, WSEventType
from app.forge.assets.picker import format_assets_for_prompt
from app.forge.build.code_output import ParsedCodeOutput
from app.forge.build.integration import (
    format_project_repair_input,
    load_stored_project_source,
    parse_llm_code_output,
    run_project_build_loop,
    with_design_routing,
)
from app.forge.build.routing import routing_from_design_doc, should_use_vite_pipeline
from app.forge.code_candidate import claim_candidate_version
from app.forge.design_doc import coerce_design_doc
from app.forge.engine_router import engine_scaffold
from app.forge.events import publish_event
from app.forge.prompts import (
    build_code_prompt_async,
    build_project_prompt,
    build_project_repair_prompt,
    build_repair_prompt_async,
)
from app.forge.qa.diagnose import diagnose_playtest_failure
from app.forge.reliability.artifact_gate import derive_artifact_gate
from app.hosting import serve, store
from app.models.game_version import GameVersion
from app.sandbox import get_sandbox
from app.sandbox.playtest import (
    is_permanent_infra_error,
    run_playtest,
    run_playtest_dist,
)


def _read_html(path: Any) -> str:
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="replace")


def _mask_data_uris(source: str) -> tuple[str, dict[str, str]]:
    replacements: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"__FORGE_DATA_URI_{len(replacements):04d}__"
        replacements[token] = match.group(0)
        return token

    masked = re.sub(
        r"data:[^;\"'\s]+;base64,[A-Za-z0-9+/=]+",
        replace,
        source,
    )
    return masked, replacements


async def _code_llm(
    ctx: Any,
    system: str,
    user_msg: str,
    *,
    context_summary: str | None = None,
    emit_delta: bool = False,
    kind: str | None = None,
) -> tuple[str, bool]:
    from app.forge.llm_continuation import generate_code_output

    return await generate_code_output(
        ctx,
        system,
        user_msg,
        context_summary=context_summary,
        emit_delta=emit_delta,
        kind=kind,
    )


def _continuation_context_summary(design_doc: dict[str, Any], game_title: str) -> str:
    engine = (design_doc.get("engine") or {}).get("id", "canvas")
    title = design_doc.get("title") or game_title
    return f"游戏：{title}；引擎：{engine}"


def _truncation_failure(
    *,
    attempt: int,
    design_doc: dict[str, Any],
    artifacts: list[Any],
    art_direction: dict[str, Any] | None,
    qa_diagnosis: str,
) -> dict[str, Any]:
    from app.forge.llm_continuation import OUTPUT_TRUNCATED_ERROR

    return {
        "attempt": attempt,
        "candidate_ready": False,
        "code_ok": False,
        "qa_ok": False,
        "failure_kind": "truncated",
        "playtest_errors": [OUTPUT_TRUNCATED_ERROR],
        "qa_diagnosis": qa_diagnosis,
        "design_doc": design_doc,
        "artifacts": artifacts,
        "art_direction": art_direction,
        "exhausted": False,
    }


def _omit_data_uris(html: str) -> str:
    return re.sub(
        r"data:[^;\"'\s]+;base64,[A-Za-z0-9+/=]+",
        "__DATA_URI_OMITTED_FOR_QA__",
        html,
    )[:60000]


async def execute_code_or_repair(
    ctx: Any,
    state: dict[str, Any],
    *,
    streamed_llm: Any,
    set_phase: Any,
    check_ctrl: Any,
    normalize_html: Any,
    commit_project_build: Any,
    run_finalized_exc: type[BaseException],
) -> dict[str, Any]:
    """单次 CodeQa attempt：generate 或 repair，成功则写入 candidate（不 promote）。"""
    from app.forge.assets.picker import PickedAsset
    from app.forge.tracing import observe_phase
    from app.games import services as game_services

    with observe_phase("code"):
        design_doc = coerce_design_doc(state.get("design_doc") or {}, ctx.game.title)
        entry_req = state.get("entry_requirement")
        artifacts = state.get("artifacts") or []
        art_direction = state.get("art_direction") or {}
        assets_block = ""
        if artifacts:
            picked = [
                PickedAsset(
                    asset_id=a["asset_id"],
                    filename=a["filename"],
                    kind=a["kind"],
                    description=a.get("description", a["filename"]),
                    data_uri=a["data_uri"],
                )
                for a in artifacts
            ]
            assets_block = "\n\n" + format_assets_for_prompt(picked)

        qa_errors_raw = list(state.get("playtest_errors") or [])
        from app.forge.llm_continuation import is_output_truncated_error

        # 环境类 infra（缺 Playwright 等）不应喂给 LLM「改游戏代码」
        qa_errors = [
            e
            for e in qa_errors_raw
            if not is_permanent_infra_error([str(e)]) and not is_output_truncated_error([str(e)])
        ]
        qa_diagnosis = state.get("qa_diagnosis") or ""
        attempt = int(state.get("attempt") or 0) + 1
        ctx_summary = _continuation_context_summary(design_doc, ctx.game.title)

        # P5：Memory/设计稿唯一经 ContextBuilder；assets/scaffold/repair 为任务载荷追加
        from app.forge.memory.loader import build_node_context

        entry_block = (entry_req or "").strip() or "请按已确认设计稿实现可运行游戏。"
        if settings.memory_session_summary:
            from app.forge.memory.refresh import refresh_session_summary_if_needed

            await refresh_session_summary_if_needed(ctx.s, ctx.game)
        built = await build_node_context(
            ctx.s,
            node="code" if attempt <= 1 and not entry_req else "repair",
            game=ctx.game,
            user_id=ctx.game.owner_id,
            current_input=entry_block,
            design_doc=design_doc,
        )
        base_user_msg = built.user_message
        if art_direction:
            base_user_msg += "\n\n【已确认美术实现设计稿 JSON】\n" + json.dumps(
                art_direction, ensure_ascii=False, indent=2
            )
        generation_user_msg = base_user_msg
        if assets_block:
            generation_user_msg += f"\n\n【可用内置素材】{assets_block}"
        scaffold = engine_scaffold(design_doc["engine"]["id"])
        if scaffold:
            generation_user_msg += (
                "\n\n【所选引擎最小可运行骨架（参考起点，在此基础上实现设计稿，"
                "不要照搬玩法，须替换为设计稿的实体/关卡/规则）】\n"
                f"{scaffold}"
            )

        baseline_version = state.get("candidate_version")
        if baseline_version is None and ctx.game.current_version > 0:
            baseline_version = ctx.game.current_version
        use_baseline = attempt > 1 or bool(entry_req)

        previous_html = ""
        if use_baseline and baseline_version and int(baseline_version) > 0:
            current_path = store.index_path(ctx.game.id, int(baseline_version))
            if current_path is not None and current_path.exists():
                previous_html = _read_html(current_path)

        await set_phase(ctx, RunPhase.CODE)
        last_error = "; ".join(qa_errors)
        design_routing = routing_from_design_doc(design_doc)
        engine_id = design_doc["engine"]["id"]
        use_vite = should_use_vite_pipeline(design_routing, enabled=settings.build_pipeline_enabled)

        ctrl = await check_ctrl(ctx, design_doc)
        if ctrl != "ok":
            return {
                "attempt": attempt,
                "design_doc": design_doc,
                "artifacts": artifacts,
                "art_direction": art_direction,
                "paused": ctrl == "pause",
                "failed": ctrl == "cancel",
                "candidate_ready": False,
                "code_ok": False,
            }

        stored_project: dict[str, str] | None = None
        if use_vite and previous_html and baseline_version:
            loaded = await load_stored_project_source(ctx.game.id, int(baseline_version))
            if loaded:
                stored_project = loaded

        raw_output = ""
        data_uris: dict[str, str] = {}

        if use_vite and stored_project:
            parsed_retry = ParsedCodeOutput(
                format="project",
                files=stored_project,
                routing=design_routing,
            )
            if last_error or qa_diagnosis:
                repair_parts = [base_user_msg]
                if last_error:
                    repair_parts.append(f"【自动试玩/构建错误】\n{last_error}")
                if qa_diagnosis:
                    repair_parts.append(f"【QA 根因分析】\n{qa_diagnosis}")
                repair_user = format_project_repair_input(
                    "\n\n".join(repair_parts),
                    parsed_retry,
                    last_error or qa_diagnosis,
                )
                repair_raw, truncated = await _code_llm(
                    ctx,
                    build_project_repair_prompt(engine_id, list(design_routing.dependencies)),
                    repair_user,
                    context_summary=ctx_summary,
                )
                if truncated:
                    return _truncation_failure(
                        attempt=attempt,
                        design_doc=design_doc,
                        artifacts=artifacts,
                        art_direction=art_direction,
                        qa_diagnosis=qa_diagnosis,
                    )
                parsed_retry = with_design_routing(
                    parse_llm_code_output(repair_raw, engine_id=engine_id),
                    design_routing,
                )
            raw_output = json.dumps(
                {
                    "format": "project",
                    **design_routing.to_dict(),
                    "files": parsed_retry.files,
                },
                ensure_ascii=False,
            )
        elif previous_html:
            masked_html, data_uris = _mask_data_uris(previous_html)
            repair_parts = [base_user_msg]
            if last_error:
                repair_parts.append(f"【自动试玩/构建错误】\n{last_error}")
            if qa_diagnosis:
                repair_parts.append(f"【QA 根因分析】\n{qa_diagnosis}")
            repair_parts.append(f"【当前完整 index.html】\n{masked_html}")
            user_msg = "\n\n".join(repair_parts)
            system_prompt = await build_repair_prompt_async(
                design_doc["engine"]["id"],
                hints={"run_id": str(ctx.run.id)},
                complete=lambda s, u: streamed_llm(
                    ctx, s, u, "code", emit_delta=False, kind="skill_select"
                ),
            )
            raw_output, truncated = await _code_llm(
                ctx, system_prompt, user_msg, context_summary=ctx_summary
            )
            if truncated:
                return _truncation_failure(
                    attempt=attempt,
                    design_doc=design_doc,
                    artifacts=artifacts,
                    art_direction=art_direction,
                    qa_diagnosis=qa_diagnosis,
                )
        else:
            user_msg = generation_user_msg
            if last_error:
                user_msg += f"\n\n【上次构建错误】\n{last_error}"
            if use_vite:
                system_prompt = build_project_prompt(
                    engine_id,
                    list(design_routing.dependencies),
                )
            else:
                system_prompt = await build_code_prompt_async(
                    engine_id,
                    hints={"run_id": str(ctx.run.id)},
                    complete=lambda s, u: streamed_llm(
                        ctx, s, u, "code", emit_delta=False, kind="skill_select"
                    ),
                )
            raw_output, truncated = await _code_llm(
                ctx, system_prompt, user_msg, context_summary=ctx_summary
            )
            if truncated:
                return _truncation_failure(
                    attempt=attempt,
                    design_doc=design_doc,
                    artifacts=artifacts,
                    art_direction=art_direction,
                    qa_diagnosis=qa_diagnosis,
                )

        for token, data_uri in data_uris.items():
            raw_output = raw_output.replace(token, data_uri)

        if use_vite and (stored_project or not previous_html):
            parsed = with_design_routing(
                parse_llm_code_output(raw_output, engine_id=engine_id),
                design_routing,
            )
            if parsed.format == "project":

                async def _repair_project(
                    current: ParsedCodeOutput, build_error: str
                ) -> ParsedCodeOutput:
                    repair_user = format_project_repair_input(base_user_msg, current, build_error)
                    repair_raw, truncated = await _code_llm(
                        ctx,
                        build_project_repair_prompt(engine_id, list(design_routing.dependencies)),
                        repair_user,
                        context_summary=ctx_summary,
                    )
                    if truncated:
                        from app.forge.llm_continuation import OutputTruncatedError

                        raise OutputTruncatedError()
                    return with_design_routing(
                        parse_llm_code_output(repair_raw, engine_id=engine_id),
                        design_routing,
                    )

                loop_result = await run_project_build_loop(parsed, repair_fn=_repair_project)
                if loop_result.output_truncated:
                    return _truncation_failure(
                        attempt=attempt,
                        design_doc=design_doc,
                        artifacts=artifacts,
                        art_direction=art_direction,
                        qa_diagnosis=qa_diagnosis,
                    )
                if loop_result.ok and loop_result.pipeline_result:
                    committed = await commit_project_build(
                        ctx,
                        project_result=loop_result.pipeline_result,
                        design_doc=design_doc,
                        artifacts=artifacts,
                        art_direction=art_direction,
                        attempt=int(attempt),
                    )
                    return {
                        **committed,
                        "attempt": attempt,
                        "qa_ok": False,
                        "exhausted": False,
                    }
                # Vite 内环耗尽：failure_kind=build，禁止降级 single-html
                fail_logs = ""
                if loop_result.pipeline_result:
                    fail_logs = (
                        loop_result.pipeline_result.error or loop_result.pipeline_result.logs or ""
                    )
                await publish_event(
                    ctx.run.id,
                    WSEventType.TOOL_CALL,
                    {
                        "phase": "code",
                        "tool": "build_exhausted",
                        "args": {
                            "attempt": loop_result.build_attempts,
                            "code_qa_attempt": attempt,
                        },
                        "status": "error",
                        "summary": "Vite 构建耗尽，不降级 single-html",
                    },
                )
                return {
                    "attempt": attempt,
                    "candidate_ready": False,
                    "code_ok": False,
                    "qa_ok": False,
                    "failure_kind": "build",
                    "playtest_errors": [fail_logs or last_error or "Vite 构建失败"],
                    "qa_diagnosis": qa_diagnosis,
                    "design_doc": design_doc,
                    "artifacts": artifacts,
                    "art_direction": art_direction,
                    "exhausted": False,
                }
            elif not previous_html and not stored_project:
                await publish_event(
                    ctx.run.id,
                    WSEventType.TOOL_CALL,
                    {
                        "phase": "code",
                        "tool": "build_format_mismatch",
                        "args": {
                            "expected": "project",
                            "got": parsed.format,
                            "errors": list(parsed.errors),
                        },
                        "status": "warn",
                        "summary": (
                            "build=vite 但 LLM 未返回 project JSON，本 attempt 按 build 失败处理"
                        ),
                    },
                )
                return {
                    "attempt": attempt,
                    "candidate_ready": False,
                    "code_ok": False,
                    "qa_ok": False,
                    "failure_kind": "build",
                    "playtest_errors": list(parsed.errors) or ["LLM 未返回 project JSON"],
                    "qa_diagnosis": qa_diagnosis,
                    "design_doc": design_doc,
                    "artifacts": artifacts,
                    "art_direction": art_direction,
                    "exhausted": False,
                }

        html = normalize_html(raw_output)
        from app.sandbox.tiers import tier_hints_from_design_doc

        result = await get_sandbox().execute(
            source={"index.html": html},
            hints=tier_hints_from_design_doc(design_doc),
        )
        if result.ok:
            await ctx.s.refresh(ctx.run)
            if ctx.run.status != RunStatus.RUNNING.value or ctx.run.ended_at is not None:
                raise run_finalized_exc

            version, _is_new = await claim_candidate_version(
                ctx.r,
                ctx.s,
                ctx.game,
                run_id=ctx.run.id,
                attempt=int(attempt),
            )
            artifact = f"{ctx.game.id}/{version}/index.html"
            await store.write_artifact(ctx.game.id, version, dict[str, str | bytes](result.files))
            existing_gv = await ctx.s.scalar(
                select(GameVersion).where(
                    GameVersion.game_id == ctx.game.id,
                    GameVersion.version == version,
                )
            )
            if existing_gv is None:
                ctx.s.add(
                    GameVersion(
                        game_id=ctx.game.id,
                        version=version,
                        artifact_path=artifact,
                        design_doc=design_doc,
                    )
                )
            else:
                existing_gv.artifact_path = artifact
                existing_gv.design_doc = design_doc
            await ctx.s.commit()
            await game_services.prune_old_versions(ctx.s, ctx.game)
            from app.forge.lineage import persist_candidate_revision

            await persist_candidate_revision(ctx.s, ctx.r, ctx.run.id, version)
            await ctx.s.commit()
            await publish_event(
                ctx.run.id,
                WSEventType.BUILD_DONE,
                {
                    "version": version,
                    "artifact_path": artifact,
                    "preview_url": f"/draft/{ctx.game.id}/{version}",
                    **derive_artifact_gate(build_ok=True, qa_ok=False).as_dict(),
                },
            )
            return {
                "attempt": attempt,
                "code_ok": True,
                "candidate_ready": True,
                "candidate_version": version,
                "candidate_kind": "single-html",
                "qa_ok": False,
                "exhausted": False,
                "failure_kind": None,
                "playtest_errors": [],
                "qa_diagnosis": "",
                "failed": False,
                "design_doc": design_doc,
                "artifacts": artifacts,
                "art_direction": art_direction,
                **derive_artifact_gate(build_ok=True, qa_ok=False).as_dict(),
            }

        last_error = result.error or "构建失败"
        await publish_event(
            ctx.run.id,
            WSEventType.TOOL_CALL,
            {
                "phase": "code",
                "tool": "execute_code",
                "args": {"attempt": attempt},
                "status": "error",
                "summary": last_error,
            },
        )
        return {
            "attempt": attempt,
            "candidate_ready": False,
            "code_ok": False,
            "qa_ok": False,
            "failure_kind": "build",
            "playtest_errors": [last_error],
            "qa_diagnosis": qa_diagnosis,
            "design_doc": design_doc,
            "artifacts": artifacts,
            "art_direction": art_direction,
            "exhausted": False,
        }


async def execute_playtest(
    ctx: Any,
    state: dict[str, Any],
    *,
    set_phase: Any,
    save_thumbnail: Any,
) -> dict[str, Any]:
    """对当前 candidate 跑 B 档 playtest；不写 run.status。"""
    from app.forge.tracing import observe_phase

    with observe_phase("qa"):
        design_doc = coerce_design_doc(state.get("design_doc") or {}, ctx.game.title)
        attempt = int(state.get("attempt") or 0)
        candidate_version = state.get("candidate_version")
        await set_phase(ctx, RunPhase.QA)

        if not state.get("candidate_ready") or not candidate_version:
            errors = ["无可用 candidate，跳过试玩"]
            await publish_event(
                ctx.run.id,
                WSEventType.QA_REPORT,
                {
                    "passed": False,
                    "issues": errors,
                    "log_excerpt": "",
                    "console_logs": [],
                    "playtest_mode": "playwright",
                    "attempt": attempt,
                    "failure_kind": "build",
                    "motion_signal": None,
                },
            )
            return {
                "qa_ok": False,
                "candidate_ready": False,
                "failure_kind": "build",
                "playtest_errors": errors,
                "console_logs": [],
                "motion_signal": None,
                "design_doc": design_doc,
                "attempt": attempt,
            }

        version = int(candidate_version)
        html_path = store.index_path(ctx.game.id, version)
        html = ""
        pt = None
        gate_doc = design_doc if settings.forge_acceptance_gate else None
        runtime_doc = design_doc if settings.forge_acceptance_runtime else None
        if html_path is None or not html_path.exists():
            errors = ["产物 index.html 不存在，无法试玩"]
            result_ok = False
            console_logs: list[str] = []
            failure_kind: str | None = "build"
            motion_signal = None
        elif serve.is_project_artifact(ctx.game.id, version):
            artifact_dir = store.artifact_dir(ctx.game.id, version)
            pt = await run_playtest_dist(
                artifact_dir,
                want_thumb=settings.thumbnail_enabled,
                design_doc=gate_doc,
                runtime_design_doc=runtime_doc,
            )
            result_ok = pt.ok
            errors = pt.errors
            console_logs = pt.console_logs
            failure_kind = pt.failure_kind
            motion_signal = pt.motion_signal
            html_path = artifact_dir / "index.html"
            html = _read_html(html_path) if html_path.is_file() else ""
        else:
            html = _read_html(html_path)
            pt = await run_playtest(
                html,
                want_thumb=settings.thumbnail_enabled,
                design_doc=gate_doc,
                runtime_design_doc=runtime_doc,
            )
            result_ok = pt.ok
            errors = pt.errors
            console_logs = pt.console_logs
            failure_kind = pt.failure_kind
            motion_signal = pt.motion_signal

        if not result_ok and failure_kind is None:
            failure_kind = "product"

        log_excerpt = "\n".join(console_logs[:5]) if console_logs else ""
        await publish_event(
            ctx.run.id,
            WSEventType.QA_REPORT,
            {
                "passed": result_ok,
                "issues": [] if result_ok else errors,
                "log_excerpt": log_excerpt,
                "console_logs": console_logs,
                "playtest_mode": "playwright",
                "attempt": attempt,
                "failure_kind": None if result_ok else failure_kind,
                "motion_signal": motion_signal,
            },
        )

        if result_ok:
            if pt and pt.thumbnail:
                await save_thumbnail(ctx.s, ctx.game, version, pt.thumbnail)
            return {
                "qa_ok": True,
                "playtest_errors": [],
                "console_logs": console_logs,
                "failure_kind": None,
                "motion_signal": motion_signal,
                "qa_diagnosis": "",
                "failed": False,
                "design_doc": design_doc,
                "attempt": attempt,
                "candidate_version": version,
                "candidate_ready": True,
            }

        return {
            "qa_ok": False,
            "playtest_errors": errors,
            "console_logs": console_logs,
            "failure_kind": failure_kind,
            "motion_signal": motion_signal,
            "failed": False,
            "design_doc": design_doc,
            "attempt": attempt,
            "candidate_version": version,
            "candidate_ready": True,
            "artifacts": state.get("artifacts") or [],
            "art_direction": state.get("art_direction") or {},
            "_qa_html": html,
        }


async def execute_diagnose(
    ctx: Any,
    state: dict[str, Any],
    *,
    llm: Any,
) -> dict[str, Any]:
    """对 product/build 失败做诊断；infra 不得进入本节点（由子图路由保证）。"""
    from app.forge.tracing import observe_phase

    with observe_phase("qa"):
        design_doc = coerce_design_doc(state.get("design_doc") or {}, ctx.game.title)
        errors = list(state.get("playtest_errors") or [])
        console_logs = list(state.get("console_logs") or [])
        html = state.get("_qa_html") or ""
        if not html:
            version = state.get("candidate_version")
            if version:
                path = store.index_path(ctx.game.id, int(version))
                if path is not None and path.exists():
                    html = _read_html(path)
        qa_source = _omit_data_uris(html)

        async def _call(system: str, user_msg: str) -> str:
            return await llm(ctx, system, user_msg)

        from app.forge.memory.loader import build_node_context

        if settings.memory_session_summary:
            from app.forge.memory.refresh import refresh_session_summary_if_needed

            await refresh_session_summary_if_needed(ctx.s, ctx.game)
        built = await build_node_context(
            ctx.s,
            node="diagnose",
            game=ctx.game,
            user_id=ctx.game.owner_id,
            current_input="请根据自动试玩证据诊断失败根因并给出可执行修复方案。",
            design_doc=design_doc,
        )

        diagnosis = await diagnose_playtest_failure(
            llm=_call,
            design_doc=None,
            errors=errors,
            console_logs=console_logs,
            source_excerpt=qa_source,
            memory_prefix=built.user_message,
            failure_kind=str(state.get("failure_kind") or "product"),
        )
        return {
            "qa_ok": False,
            "qa_diagnosis": diagnosis,
            "playtest_errors": errors,
            "console_logs": console_logs,
            "failure_kind": state.get("failure_kind") or "product",
            "design_doc": design_doc,
            "artifacts": state.get("artifacts") or [],
            "art_direction": state.get("art_direction") or {},
            "candidate_ready": False,
            "attempt": state.get("attempt"),
            "candidate_version": state.get("candidate_version"),
        }
