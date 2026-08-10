"""生成主图：LangGraph 固定 DAG plan→[HITL]→art→code↔qa→done（docs/02/03）。

支持：策划修订后再次确认、节点间 pause/cancel、code/qa 自动诊断重试、
重试耗尽后明确失败、skills 约定注入。策划确认后不再插入被动 HITL。
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

import redis.asyncio as redis
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.enums import RunPhase, RunStatus, WSEventType
from app.forge import control as run_ctrl
from app.forge import state as ckpt
from app.forge.assets.picker import asset_pick, format_assets_for_prompt
from app.forge.design_doc import (
    coerce_design_doc,
    design_doc_to_text,
    parse_design_doc,
    validate_design_doc,
)
from app.forge.events import publish_event
from app.forge.phase_labels import phase_start_payload
from app.forge.prompts import (
    CODE_PROMPT,
    CODE_REPAIR_PROMPT,
    PLAN_PROMPT,
    PLAN_REVISE_PROMPT,
    QA_PROMPT,
)
from app.forge.tracing import observe_phase, observe_run
from app.hosting import store
from app.llm import client as llm_client
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.generation_run import GenerationRun
from app.sandbox import get_sandbox
from app.sandbox.playtest import run_playtest

PLAN_MAX_ATTEMPTS = 2

log = logging.getLogger(__name__)


class ForgeState(TypedDict, total=False):
    run_id: str
    resume: bool
    entry_phase: str
    entry_requirement: str | None
    decision: str | None
    modify_text: str | None
    design_doc: dict[str, Any] | str
    artifacts: list[dict[str, str]]
    code_ok: bool
    qa_ok: bool
    qa_attempt: int
    qa_retry: bool
    playtest_errors: list[str]
    qa_diagnosis: str
    failed: bool
    error: str
    hitl_stop: bool
    paused: bool


class _Ctx:
    def __init__(
        self, s: AsyncSession, r: redis.Redis, run: GenerationRun, game: Game
    ) -> None:
        self.s = s
        self.r = r
        self.run = run
        self.game = game


async def _llm(ctx: _Ctx, system: str, user_msg: str) -> str:
    stage = ctx.run.phase or "llm"
    started = time.monotonic()
    # 只记长度不记原文：prompt/响应内容属敏感且冗长，按 docs 约定不落盘
    log.info("llm call start", extra={"stage": stage, "prompt_len": len(user_msg)})
    try:
        content, usage, prov = await llm_client.call_llm(
            ctx.s,
            ctx.r,
            ctx.run.user_id,
            ctx.run.llm_config_id,
            system,
            user_msg,
            game_id=ctx.game.id,
            run_id=ctx.run.id,
        )
    except Exception:
        duration = round(time.monotonic() - started, 3)
        log.exception("llm call failed", extra={"stage": stage, "duration": duration})
        raise
    duration = round(time.monotonic() - started, 3)
    log.info(
        "llm call complete",
        extra={
            "stage": stage,
            "duration": duration,
            "resp_len": len(content),
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        },
    )
    await publish_event(
        ctx.run.id,
        WSEventType.LLM_CALL,
        {
            "phase": ctx.run.phase,
            "model": "user-config",
            "provider": prov.value,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        },
    )
    return content


async def _set_phase(ctx: _Ctx, phase: RunPhase) -> None:
    ctx.run.phase = phase.value
    await ctx.s.commit()
    await publish_event(
        ctx.run.id,
        WSEventType.PHASE_START,
        phase_start_payload(phase.value),
    )


async def _fail(ctx: _Ctx, message: str, *, code: str = "SANDBOX_FAILED") -> None:
    ctx.run.status = RunStatus.FAILED.value
    ctx.run.ended_at = datetime.now(UTC)
    await ctx.s.commit()
    await publish_event(
        ctx.run.id,
        WSEventType.ERROR,
        {"code": code, "message": message, "fatal": True},
    )


async def _pause_hitl(
    ctx: _Ctx, node: str, design_doc: dict[str, Any], extra: dict | None = None
) -> None:
    ctx.run.status = RunStatus.PAUSED.value
    await ctx.s.commit()
    payload = {
        "node": node,
        "design_doc": design_doc,
        "action_url": f"/api/v1/games/{ctx.game.id}/runs/{ctx.run.id}/hitl/resolve",
    }
    if extra:
        payload.update(extra)
    await publish_event(ctx.run.id, WSEventType.HITL_WAIT, payload)


async def _check_ctrl(
    ctx: _Ctx, design_doc: dict[str, Any] | str
) -> Literal["ok", "pause", "cancel"]:
    flag = await run_ctrl.poll_control(ctx.r, ctx.run.id)
    if flag == "cancel":
        await _fail(ctx, "用户取消", code="CANCELLED")
        return "cancel"
    if flag == "pause":
        doc = coerce_design_doc(design_doc, ctx.game.title)
        await ckpt.save_state(
            ctx.r, ctx.run.id, {"phase": "user_pause", "design_doc": doc}
        )
        ctx.run.status = RunStatus.PAUSED.value
        await ctx.s.commit()
        await run_ctrl.clear_control(ctx.r, ctx.run.id)
        return "pause"
    return "ok"


def _build_graph(ctx: _Ctx) -> Any:
    async def generate_design_doc(
        system_prompt: str, user_msg: str
    ) -> dict[str, Any]:
        """生成并真实校验策划稿；格式错误时把具体问题反馈给模型自修复。"""
        issues: list[str] = []
        design_doc: dict[str, Any] = {}
        for attempt in range(1, PLAN_MAX_ATTEMPTS + 1):
            attempt_msg = user_msg
            if issues:
                attempt_msg += (
                    "\n\n【上次设计稿校验失败】\n- "
                    + "\n- ".join(issues)
                    + "\n请返回修复后的完整 JSON，不要只返回修改片段。"
                )
            raw = await _llm(ctx, system_prompt, attempt_msg)
            design_doc = parse_design_doc(raw, ctx.game.title)
            issues = validate_design_doc(design_doc)
            if not issues:
                return design_doc
            await publish_event(
                ctx.run.id,
                WSEventType.TOOL_CALL,
                {
                    "phase": "plan",
                    "tool": "design_lint",
                    "args": {"attempt": attempt},
                    "status": "error",
                    "summary": "; ".join(issues[:8]),
                },
            )
        raise ValueError("策划稿结构校验失败：" + "; ".join(issues))

    async def route_start(
        state: ForgeState,
    ) -> Literal["plan", "revise_plan", "art", "code"]:
        if not state.get("resume"):
            if state.get("entry_phase") == "code":
                return "code"
            return "plan"

        st = await ckpt.load_state(ctx.r, ctx.run.id) or {}
        phase = st.get("phase")
        if phase == "plan_confirm":
            if state.get("decision") == "modify" and state.get("modify_text"):
                return "revise_plan"
            return "art"
        # 兼容升级前已经停在 sandbox/qa HITL 的历史任务；新任务在策划确认后
        # 不再请求人工介入，而是在预算内自动修复，耗尽后直接报告失败。
        if st.get("phase") in ("sandbox_failed", "qa_failed", "user_pause"):
            return "code" if st.get("phase") != "user_pause" else "art"
        return "art"

    async def plan_node(state: ForgeState) -> dict:
        with observe_phase("plan"):
            await _set_phase(ctx, RunPhase.PLAN)
            design_doc = await generate_design_doc(
                PLAN_PROMPT, f"【用户原始需求】\n{ctx.run.requirement}"
            )
            ctrl = await _check_ctrl(ctx, design_doc)
            if ctrl != "ok":
                return {
                    "design_doc": design_doc,
                    "paused": ctrl == "pause",
                    "failed": ctrl == "cancel",
                }
            await publish_event(
                ctx.run.id,
                WSEventType.TOOL_CALL,
                {
                    "phase": "plan",
                    "tool": "design_lint",
                    "args": {},
                    "status": "ok",
                    "summary": "策划稿完成",
                },
            )
            await ckpt.save_state(
                ctx.r,
                ctx.run.id,
                {"phase": "plan_confirm", "design_doc": design_doc},
            )
            await _pause_hitl(ctx, "plan_confirm", design_doc)
            return {"design_doc": design_doc, "hitl_stop": True}

    async def revise_plan_node(state: ForgeState) -> dict:
        with observe_phase("plan"):
            await _set_phase(ctx, RunPhase.PLAN)
            current_doc = coerce_design_doc(
                state.get("design_doc") or {}, ctx.game.title
            )
            user_msg = (
                "【当前完整设计稿 JSON】\n"
                f"{design_doc_to_text(current_doc)}\n\n"
                "【用户修改意见】\n"
                f"{state.get('modify_text') or ''}"
            )
            design_doc = await generate_design_doc(PLAN_REVISE_PROMPT, user_msg)
            ctrl = await _check_ctrl(ctx, design_doc)
            if ctrl != "ok":
                return {
                    "design_doc": design_doc,
                    "paused": ctrl == "pause",
                    "failed": ctrl == "cancel",
                }
            await publish_event(
                ctx.run.id,
                WSEventType.TOOL_CALL,
                {
                    "phase": "plan",
                    "tool": "design_lint",
                    "args": {"revision": True},
                    "status": "ok",
                    "summary": "策划稿已按修改意见重构",
                },
            )
            await ckpt.save_state(
                ctx.r,
                ctx.run.id,
                {"phase": "plan_confirm", "design_doc": design_doc},
            )
            # 用户要求只确认策划案；修改后的策划案仍属于策划确认范围。
            await _pause_hitl(ctx, "plan_confirm", design_doc)
            return {
                "design_doc": design_doc,
                "decision": None,
                "modify_text": None,
                "hitl_stop": True,
            }

    async def art_node(state: ForgeState) -> dict:
        with observe_phase("art"):
            design_doc = coerce_design_doc(
                state.get("design_doc") or {}, ctx.game.title
            )
            design_text = design_doc_to_text(design_doc)
            await _set_phase(ctx, RunPhase.ART)
            ctrl = await _check_ctrl(ctx, design_doc)
            if ctrl != "ok":
                return {
                    "design_doc": design_doc,
                    "paused": ctrl == "pause",
                    "failed": ctrl == "cancel",
                }
            assets = asset_pick(design_text)
            artifacts = [
                {
                    "asset_id": a.asset_id,
                    "filename": a.filename,
                    "kind": a.kind,
                    "data_uri": a.data_uri,
                }
                for a in assets
            ]
            await publish_event(
                ctx.run.id,
                WSEventType.TOOL_CALL,
                {
                    "phase": "art",
                    "tool": "asset_pick",
                    "args": {"count": len(artifacts)},
                    "status": "ok",
                    "summary": f"已选 {len(artifacts)} 个内置素材",
                    "artifacts": artifacts,
                },
            )
            return {"design_doc": design_doc, "artifacts": artifacts}

    async def code_node(state: ForgeState) -> dict:
        with observe_phase("code"):
            design_doc = coerce_design_doc(
                state.get("design_doc") or {}, ctx.game.title
            )
            design_text = design_doc_to_text(design_doc)
            entry_req = state.get("entry_requirement")
            assets_block = ""
            artifacts = state.get("artifacts") or []
            if artifacts:
                from app.forge.assets.picker import PickedAsset

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

            qa_errors = state.get("playtest_errors") or []
            qa_diagnosis = state.get("qa_diagnosis") or ""
            base_user_msg = f"【已确认设计稿 JSON】\n{design_text}"
            if entry_req:
                base_user_msg += f"\n\n【本次实现变更要求】\n{entry_req}"
            generation_user_msg = base_user_msg
            if assets_block:
                generation_user_msg += f"\n\n【可用内置素材】{assets_block}"

            # QA 失败或对已有版本做修改时，以当前可运行版本为修复基线，避免每次
            # 都从零生成造成已通过功能回归。首次构建则仍走完整生成提示词。
            previous_html = ""
            if (qa_errors or entry_req) and ctx.game.current_version > 0:
                current_path = store.index_path(
                    ctx.game.id, ctx.game.current_version
                )
                if current_path is not None and current_path.exists():
                    previous_html = current_path.read_text(encoding="utf-8")

            def normalize_html(raw: str) -> str:
                html = (raw or "").strip()
                if html.startswith("```"):
                    first_newline = html.find("\n")
                    html = html[first_newline + 1 :] if first_newline >= 0 else html[3:]
                    if html.rstrip().endswith("```"):
                        html = html.rstrip()[:-3].rstrip()
                lower = html.lower()
                start = lower.find("<!doctype html")
                if start >= 0:
                    html = html[start:]
                    lower = html.lower()
                end = lower.rfind("</html>")
                if end >= 0:
                    html = html[: end + len("</html>")]
                return html.strip()

            def mask_data_uris(source: str) -> tuple[str, dict[str, str]]:
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

            await _set_phase(ctx, RunPhase.CODE)
            last_error = "; ".join(qa_errors)
            for attempt in range(1, settings.code_max_retries + 1):
                ctrl = await _check_ctrl(ctx, design_doc)
                if ctrl != "ok":
                    return {
                        "design_doc": design_doc,
                        "artifacts": artifacts,
                        "paused": ctrl == "pause",
                        "failed": ctrl == "cancel",
                        "code_ok": False,
                    }

                if previous_html:
                    masked_html, data_uris = mask_data_uris(previous_html)
                    repair_parts = [base_user_msg]
                    if last_error:
                        repair_parts.append(f"【自动试玩/构建错误】\n{last_error}")
                    if qa_diagnosis:
                        repair_parts.append(f"【QA 根因分析】\n{qa_diagnosis}")
                    repair_parts.append(
                        f"【当前完整 index.html】\n{masked_html}"
                    )
                    user_msg = "\n\n".join(repair_parts)
                    system_prompt = CODE_REPAIR_PROMPT
                else:
                    data_uris = {}
                    user_msg = generation_user_msg
                    if last_error:
                        user_msg += f"\n\n【上次构建错误】\n{last_error}"
                    system_prompt = CODE_PROMPT

                html = normalize_html(await _llm(ctx, system_prompt, user_msg))
                for token, data_uri in data_uris.items():
                    html = html.replace(token, data_uri)
                result = await get_sandbox().execute(source={"index.html": html})
                if result.ok:
                    from app.games import services as game_services

                    ctx.game.current_version += 1
                    version = ctx.game.current_version
                    artifact = f"{ctx.game.id}/{version}/index.html"
                    await store.write_artifact(ctx.game.id, version, result.files)
                    ctx.s.add(
                        GameVersion(
                            game_id=ctx.game.id,
                            version=version,
                            artifact_path=artifact,
                            design_doc=design_doc,
                        )
                    )
                    await ctx.s.commit()
                    await game_services.prune_old_versions(ctx.s, ctx.game)
                    await publish_event(
                        ctx.run.id,
                        WSEventType.BUILD_DONE,
                        {
                            "version": version,
                            "artifact_path": artifact,
                            "preview_url": f"/draft/{ctx.game.id}/{version}",
                        },
                    )
                    return {
                        "code_ok": True,
                        "qa_ok": False,
                        "qa_retry": False,
                        "playtest_errors": [],
                        "qa_diagnosis": "",
                        "failed": False,
                        "design_doc": design_doc,
                        "artifacts": artifacts,
                    }

                last_error = result.error or "构建失败"
                previous_html = html
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

            # 策划确认后不再增加人工确认点；自动修复预算耗尽即明确结束任务。
            await ckpt.save_state(
                ctx.r,
                ctx.run.id,
                {
                    "phase": "sandbox_failed",
                    "design_doc": design_doc,
                    "error": last_error,
                },
            )
            await _fail(
                ctx,
                f"代码构建自动修复 {settings.code_max_retries} 次后仍失败：{last_error}",
                code="CODE_RETRY_EXHAUSTED",
            )
            return {
                "code_ok": False,
                "failed": True,
                "design_doc": design_doc,
                "error": last_error,
                "artifacts": artifacts,
            }

    async def qa_node(state: ForgeState) -> dict:
        with observe_phase("qa"):
            design_doc = coerce_design_doc(
                state.get("design_doc") or {}, ctx.game.title
            )
            qa_attempt = state.get("qa_attempt", 0) + 1
            await _set_phase(ctx, RunPhase.QA)

            html_path = store.index_path(ctx.game.id, ctx.game.current_version)
            html = ""
            if html_path is None or not html_path.exists():
                errors = ["产物 index.html 不存在，无法试玩"]
                result_ok = False
                console_logs: list[str] = []
            else:
                html = html_path.read_text(encoding="utf-8")
                pt = await run_playtest(html)
                result_ok = pt.ok
                errors = pt.errors
                console_logs = pt.console_logs

            log_excerpt = "\n".join(console_logs[:5]) if console_logs else ""
            await publish_event(
                ctx.run.id,
                WSEventType.QA_REPORT,
                {
                    "passed": result_ok,
                    "issues": [] if result_ok else errors,
                    "log_excerpt": log_excerpt,
                    "console_logs": console_logs,
                    "playtest_mode": "sandbox",
                },
            )

            if result_ok:
                # 自动试玩已给出确定性通过结果，无需再调用 LLM 做无效摘要。
                return {
                    "qa_ok": True,
                    "qa_retry": False,
                    "playtest_errors": [],
                    "qa_diagnosis": "",
                    "failed": False,
                    "design_doc": design_doc,
                    "qa_attempt": qa_attempt,
                }

            if qa_attempt < settings.qa_max_retries:
                qa_source = re.sub(
                    r"data:[^;\"'\s]+;base64,[A-Za-z0-9+/=]+",
                    "__DATA_URI_OMITTED_FOR_QA__",
                    html,
                )[:60000]
                diagnosis_input = (
                    "【已确认设计稿 JSON】\n"
                    f"{design_doc_to_text(design_doc)}\n\n"
                    "【自动试玩错误】\n"
                    f"{json.dumps(errors, ensure_ascii=False, indent=2)}\n\n"
                    "【控制台日志】\n"
                    f"{chr(10).join(console_logs[:20])[:6000] or '无控制台日志'}\n\n"
                    "【当前 HTML 源码（data URI 已省略）】\n"
                    f"{qa_source or '源码不可用'}"
                )
                try:
                    diagnosis = await _llm(ctx, QA_PROMPT, diagnosis_input)
                except Exception:
                    # QA 诊断是修复增强项，不应因诊断模型偶发失败而阻断确定性的
                    # 自动重试。降级为包含原始证据的结构化诊断继续修复。
                    diagnosis = json.dumps(
                        {
                            "summary": "QA 诊断调用失败，依据自动试玩原始错误继续修复",
                            "root_causes": errors,
                            "required_fixes": [
                                {
                                    "priority": "P0",
                                    "location": "根据自动试玩错误定位",
                                    "change": "逐项修复错误并保持完整游戏状态闭环",
                                    "expected_result": "自动试玩不再出现上述错误",
                                }
                            ],
                            "regression_checks": [
                                "重新验证菜单、核心操作、关卡推进、胜负与重开"
                            ],
                        },
                        ensure_ascii=False,
                    )
                return {
                    "qa_ok": False,
                    "qa_attempt": qa_attempt,
                    "qa_retry": True,
                    "playtest_errors": errors,
                    "qa_diagnosis": diagnosis,
                    "failed": False,
                    "design_doc": design_doc,
                    "artifacts": state.get("artifacts") or [],
                }

            await ckpt.save_state(
                ctx.r,
                ctx.run.id,
                {
                    "phase": "qa_failed",
                    "design_doc": design_doc,
                    "qa": "; ".join(errors),
                },
            )
            await _fail(
                ctx,
                f"自动试玩修复 {settings.qa_max_retries} 轮后仍未通过：{'; '.join(errors)}",
                code="QA_RETRY_EXHAUSTED",
            )
            return {
                "qa_ok": False,
                "qa_retry": False,
                "failed": True,
                "design_doc": design_doc,
                "qa_attempt": qa_attempt,
                "playtest_errors": errors,
                "qa_diagnosis": state.get("qa_diagnosis") or "",
            }

    async def done_node(state: ForgeState) -> dict:
        with observe_phase("done"):
            ctx.run.status = RunStatus.DONE.value
            ctx.run.phase = RunPhase.DONE.value
            ctx.run.ended_at = datetime.now(UTC)
            await ctx.s.commit()
            await ckpt.clear_state(ctx.r, ctx.run.id)
            await run_ctrl.clear_control(ctx.r, ctx.run.id)
            await publish_event(
                ctx.run.id,
                WSEventType.DONE,
                {
                    "run_id": str(ctx.run.id),
                    "game_id": str(ctx.game.id),
                    "version": ctx.game.current_version,
                    "preview_url": f"/draft/{ctx.game.id}/{ctx.game.current_version}",
                },
            )
            return {}

    def after_plan(state: ForgeState) -> Literal["__end__"]:
        return END

    def after_art(state: ForgeState) -> Literal["code", "__end__"]:
        if state.get("paused") or state.get("failed") or state.get("hitl_stop"):
            return END
        return "code"

    def after_code(state: ForgeState) -> Literal["qa", "__end__"]:
        if state.get("code_ok"):
            return "qa"
        return END

    def after_qa(state: ForgeState) -> Literal["done", "code", "__end__"]:
        if state.get("qa_ok"):
            return "done"
        if state.get("qa_retry"):
            return "code"
        return END

    g = StateGraph(ForgeState)
    g.add_node("plan", plan_node)
    g.add_node("revise_plan", revise_plan_node)
    g.add_node("art", art_node)
    g.add_node("code", code_node)
    g.add_node("qa", qa_node)
    g.add_node("done", done_node)
    g.add_conditional_edges(
        START,
        route_start,
        {
            "plan": "plan",
            "revise_plan": "revise_plan",
            "art": "art",
            "code": "code",
        },
    )
    g.add_conditional_edges("plan", after_plan, {END: END})
    g.add_conditional_edges("revise_plan", after_plan, {END: END})
    g.add_conditional_edges("art", after_art, {"code": "code", END: END})
    g.add_conditional_edges("code", after_code, {"qa": "qa", END: END})
    g.add_conditional_edges("qa", after_qa, {"done": "done", "code": "code", END: END})
    g.add_edge("done", END)
    return g.compile()


async def run_generation(
    ctx: dict,
    run_id: uuid.UUID,
    *,
    resume: bool = False,
    decision: str | None = None,
    modify_text: str | None = None,
) -> None:
    from app.core import db as dbmod
    from app.core.logging import bind_log_context, clear_log_context

    stage = "resume_run" if resume else "execute_run"
    # 绑定请求级字段：trace_id/run_id 先绑（user_id 待 run 加载后补），formatter
    # 会把它们写入本请求内每条日志顶层，便于跨节点串联「谁、哪次请求、跑到哪一步」。
    bind_log_context(trace_id=uuid.uuid4().hex[:12], run_id=str(run_id))
    started = time.monotonic()
    log.info("request received", extra={"stage": stage})
    r: redis.Redis = ctx["redis"]
    try:
        async with dbmod.SessionLocal() as s:
            run = await s.get(GenerationRun, run_id)
            if run is None:
                log.warning("run not found", extra={"stage": stage})
                return
            bind_log_context(user_id=str(run.user_id))
            game = await s.get(Game, run.game_id)
            if game is None:
                log.warning("game not found", extra={"stage": stage})
                return
            # 终态守卫：已被取消(FAILED)/完成(DONE)/已置 ended_at 的 run 直接跳过，
            # 防止 worker 消费到针对该 run 的残留或重投消息时，把一个被取消的 run
            # 又改回 RUNNING 继续跑（HITL 等待中点「终止」后 worker 仍复活的根因）。
            # 合法的复活路径（retry_run / dev_requeue / HITL resolve）都会在入队前
            # 把 status 重置为 RUNNING 并清空 ended_at，故不会误伤。
            if (
                run.status in (RunStatus.FAILED.value, RunStatus.DONE.value)
                or run.ended_at is not None
            ):
                log.warning(
                    "skip finalized run", extra={"stage": stage, "status": run.status}
                )
                return
            try:
                with observe_run(str(run_id)):
                    await _run_body(
                        s, r, run, game, run_id, resume, decision, modify_text
                    )
                duration = round(time.monotonic() - started, 3)
                log.info(
                    "request completed",
                    extra={"stage": stage, "duration": duration},
                )
            except Exception as e:
                duration = round(time.monotonic() - started, 3)
                log.exception(
                    "request failed",
                    extra={"stage": stage, "duration": duration},
                )
                run.status = RunStatus.FAILED.value
                run.ended_at = datetime.now(UTC)
                await s.commit()
                await publish_event(
                    run_id,
                    WSEventType.ERROR,
                    {"code": "RUN_FAILED", "message": str(e), "fatal": True},
                )
    finally:
        clear_log_context()


async def _run_body(
    s: AsyncSession,
    r: redis.Redis,
    run: GenerationRun,
    game: Game,
    run_id: uuid.UUID,
    resume: bool,
    decision: str | None,
    modify_text: str | None,
) -> None:
    design_doc: dict[str, Any] | str = ""
    entry_phase = getattr(run, "entry_phase", "plan") or "plan"
    entry_requirement: str | None = None
    if resume:
        st = await ckpt.load_state(r, run_id) or {}
        design_doc = st.get("design_doc") or run.requirement
        run.status = RunStatus.RUNNING.value
        await s.commit()
    elif entry_phase == "code" and game.current_version > 0:
        gv = await s.scalar(
            select(GameVersion).where(
                GameVersion.game_id == game.id,
                GameVersion.version == game.current_version,
            )
        )
        if gv and gv.design_doc:
            design_doc = gv.design_doc
        entry_requirement = run.requirement

    forge_ctx = _Ctx(s, r, run, game)
    graph = _build_graph(forge_ctx)
    initial: ForgeState = {
        "run_id": str(run_id),
        "resume": resume,
        "decision": decision,
        "modify_text": modify_text,
        "design_doc": design_doc,
        "entry_phase": entry_phase,
        "entry_requirement": entry_requirement,
    }
    await graph.ainvoke(initial)
