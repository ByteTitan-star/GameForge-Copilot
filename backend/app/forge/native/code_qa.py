"""Native Engine CodeQa 节点：Godot template-first generate / repair。

【本文件 = CodeQaLoop 阅读顺序第 8 步选读 · 可跳过】
────────────────────────────────────────
Web 路线（canvas/phaser/vite）走 code_qa_exec 主路径；
Godot 等原生引擎从此处分叉，但仍复用同一 CodeQaLoop 子图边。
3 小时上手若只关心 Web 生成，跳过本文件即可（见 ADR-13）。
"""

from __future__ import annotations

from typing import Any

from app.enums import RunPhase, RunStatus, WSEventType
from app.forge.events import publish_event
from app.forge.native.codegen import (
    format_godot_repair_input,
    load_stored_godot_project,
    materialize_godot_project,
    parse_godot_code_output,
)
from app.forge.native.engine_spec import EngineFamily, get_engine_spec
from app.forge.native.metrics import is_native_repair_round, record_native_repair
from app.forge.prompts import build_godot_code_prompt, build_godot_repair_prompt


async def execute_native_code_or_repair(
    ctx: Any,
    state: dict[str, Any],
    *,
    engine_id: str,
    design_doc: dict[str, Any],
    streamed_llm: Any,
    set_phase: Any,
    commit_native_build: Any,
    run_finalized_exc: type[BaseException],
    code_llm: Any,
    truncation_failure: Any,
    base_user_msg: str,
    ctx_summary: str,
    attempt: int,
    artifacts: list[Any],
    art_direction: dict[str, Any],
    qa_errors: list[str],
    qa_diagnosis: str,
    baseline_version: Any,
    entry_req: Any,
) -> dict[str, Any]:
    from app.forge.tracing import observe_phase

    spec = get_engine_spec(engine_id)
    if spec is None or spec.family is not EngineFamily.NATIVE:
        return {
            "attempt": attempt,
            "candidate_ready": False,
            "code_ok": False,
            "failure_kind": "build",
            "playtest_errors": [f"native engine unavailable: {engine_id}"],
            "design_doc": design_doc,
            "artifacts": artifacts,
            "art_direction": art_direction,
        }

    with observe_phase("code"):
        await set_phase(ctx, RunPhase.CODE)
        last_error = "; ".join(qa_errors)
        repair_round = is_native_repair_round(attempt=attempt, entry_req=entry_req)
        if repair_round:
            record_native_repair(engine_id, event="attempted", round=attempt)
        use_baseline = attempt > 1 or bool(entry_req)
        stored_overlay: dict[str, str] = {}
        if use_baseline and baseline_version and int(baseline_version) > 0:
            stored_overlay = await load_stored_godot_project(ctx.game.id, int(baseline_version))

        if stored_overlay and (last_error or qa_diagnosis):
            user_msg = format_godot_repair_input(
                base_user_msg,
                overlay=stored_overlay,
                error_text=last_error,
                diagnosis=qa_diagnosis,
            )
            system_prompt = build_godot_repair_prompt()
        else:
            user_msg = base_user_msg
            if last_error:
                user_msg += f"\n\n【上次构建错误】\n{last_error}"
            system_prompt = build_godot_code_prompt()

        raw_output, truncated = await code_llm(
            ctx, system_prompt, user_msg, context_summary=ctx_summary
        )
        if truncated:
            if repair_round:
                record_native_repair(engine_id, event="codegen_fail", round=attempt)
            return truncation_failure(
                attempt=attempt,
                design_doc=design_doc,
                artifacts=artifacts,
                art_direction=art_direction,
                qa_diagnosis=qa_diagnosis,
            )

        parsed = parse_godot_code_output(raw_output)
        if parsed.errors or not parsed.files:
            await publish_event(
                ctx.run.id,
                WSEventType.TOOL_CALL,
                {
                    "phase": "code",
                    "tool": "godot_format_mismatch",
                    "args": {"errors": list(parsed.errors)},
                    "status": "warn",
                    "summary": "godot-project JSON 校验失败",
                },
            )
            if repair_round:
                record_native_repair(engine_id, event="codegen_fail", round=attempt)
            return {
                "attempt": attempt,
                "candidate_ready": False,
                "code_ok": False,
                "qa_ok": False,
                "failure_kind": "build",
                "playtest_errors": list(parsed.errors) or ["LLM 未返回合法 godot-project"],
                "qa_diagnosis": qa_diagnosis,
                "design_doc": design_doc,
                "artifacts": artifacts,
                "art_direction": art_direction,
                "exhausted": False,
            }

        project_files = materialize_godot_project(parsed.files)
        await ctx.s.refresh(ctx.run)
        if ctx.run.status != RunStatus.RUNNING.value or ctx.run.ended_at is not None:
            raise run_finalized_exc

        committed = await commit_native_build(
            ctx,
            files=project_files,
            design_doc=design_doc,
            artifacts=artifacts,
            art_direction=art_direction,
            attempt=int(attempt),
            engine_id=engine_id,
        )
        if repair_round:
            record_native_repair(engine_id, event="codegen_ok", round=attempt)
        return {
            **committed,
            "attempt": attempt,
            "qa_ok": False,
            "exhausted": False,
        }
