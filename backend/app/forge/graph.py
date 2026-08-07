"""生成主图：LangGraph 固定 DAG plan→[HITL]→art→code→qa→done（docs/02/03）。

支持：节点间 pause/cancel、code/qa 重试、沙箱失败 HITL、skills 约定注入。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal, TypedDict

import redis.asyncio as redis
from langgraph.graph import END, START, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.enums import LLMProvider, RunPhase, RunStatus, WSEventType
from app.forge import control as run_ctrl
from app.forge import state as ckpt
from app.forge.assets.picker import asset_pick, format_assets_for_prompt
from app.forge.design_doc import coerce_design_doc, design_doc_to_text, parse_design_doc
from app.forge.events import publish_event
from app.forge.phase_labels import phase_start_payload
from app.forge.skills import load_skill
from app.forge.tracing import observe_phase, observe_run
from app.hosting import store
from app.llm import client as llm_client
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.generation_run import GenerationRun
from app.sandbox import get_sandbox
from app.sandbox.playtest import run_playtest

_CONV = load_skill("conventions.md")
_PLAYTEST = load_skill("playtest.md")
PLAN_PROMPT = (
    "你是游戏策划，把用户需求转成结构化设计稿。"
    "只输出 JSON，不要 markdown 解释。字段：title, gameplay, controls, levels（字符串数组）。"
)
ART_PROMPT = "按设计稿产出美术素材清单（图标/精灵/背景）。输出纯文本。"
CODE_PROMPT = (
    "按设计稿生成一个自包含的 HTML5 小游戏：单 index.html，无外部依赖，无网络。"
    "只输出 HTML 源码，不要解释。\n\n"
    f"工程约定：\n{_CONV}"
)
QA_PROMPT = (
    "质检辅助：试玩已在沙箱完成，以下是自动化结果。"
    "若已通过可忽略；若失败请阅读 errors 协助修复方向。"
)


class ForgeState(TypedDict, total=False):
    run_id: str
    resume: bool
    decision: str | None
    modify_text: str | None
    design_doc: dict[str, Any] | str
    artifacts: list[dict[str, str]]
    code_ok: bool
    qa_ok: bool
    qa_attempt: int
    qa_retry: bool
    playtest_errors: list[str]
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
    content, usage = await llm_client.call_llm(
        ctx.s,
        ctx.r,
        ctx.run.user_id,
        ctx.run.llm_config_id,
        system,
        user_msg,
        game_id=ctx.game.id,
        run_id=ctx.run.id,
    )
    await publish_event(
        ctx.run.id,
        WSEventType.LLM_CALL,
        {
            "phase": ctx.run.phase,
            "model": "user-config",
            "provider": LLMProvider.ANTHROPIC.value,
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
    async def route_start(state: ForgeState) -> Literal["plan", "art", "code"]:
        if not state.get("resume"):
            return "plan"
        # sandbox/qa HITL 续跑直接进 code
        st = await ckpt.load_state(ctx.r, ctx.run.id) or {}
        if st.get("phase") in ("sandbox_failed", "qa_failed", "user_pause"):
            return "code" if st.get("phase") != "user_pause" else "art"
        return "art"

    async def plan_node(state: ForgeState) -> dict:
        with observe_phase("plan"):
            await _set_phase(ctx, RunPhase.PLAN)
            raw = await _llm(ctx, PLAN_PROMPT, ctx.run.requirement)
            design_doc = parse_design_doc(raw, ctx.game.title)
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

    async def art_node(state: ForgeState) -> dict:
        with observe_phase("art"):
            design_doc = coerce_design_doc(
                state.get("design_doc") or {}, ctx.game.title
            )
            design_text = design_doc_to_text(design_doc)
            if state.get("decision") == "modify" and state.get("modify_text"):
                design_text = f"{design_text}\n\n用户修改意见：{state['modify_text']}"
                design_doc = parse_design_doc(design_text, ctx.game.title)
            await _set_phase(ctx, RunPhase.ART)
            await _llm(ctx, ART_PROMPT, design_text)
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
            qa_err = state.get("playtest_errors") or []
            qa_hint = ""
            if qa_err:
                qa_hint = f"\n\nQA 试玩失败，请修复：{'; '.join(qa_err)}"
            await _set_phase(ctx, RunPhase.CODE)
            last_err = qa_hint.strip() or ""
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
                user_msg = design_text + assets_block
                if attempt > 1 and last_err:
                    user_msg = f"{user_msg}\n\n上次构建/试玩错误：{last_err}\n请修复。"
                elif qa_hint:
                    user_msg = f"{user_msg}{qa_hint}"
                html = await _llm(ctx, CODE_PROMPT, user_msg)
                # 粗剥 markdown 围栏
                if "```" in html:
                    parts = html.split("```")
                    html = parts[1] if len(parts) > 1 else html
                    if html.lstrip().startswith("html"):
                        html = html.lstrip()[4:]
                result = await get_sandbox().execute(source={"index.html": html.strip()})
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
                    return {"code_ok": True, "design_doc": design_doc, "artifacts": artifacts}
                last_err = result.error or "构建失败"
                await publish_event(
                    ctx.run.id,
                    WSEventType.TOOL_CALL,
                    {
                        "phase": "code",
                        "tool": "execute_code",
                        "args": {"attempt": attempt},
                        "status": "error",
                        "summary": last_err,
                    },
                )
            # 重试耗尽 → HITL
            await ckpt.save_state(
                ctx.r,
                ctx.run.id,
                {"phase": "sandbox_failed", "design_doc": design_doc, "error": last_err},
            )
            await _pause_hitl(
                ctx,
                "sandbox_failed",
                design_doc,
                {"error": last_err, "retries": settings.code_max_retries},
            )
            return {
                "code_ok": False,
                "hitl_stop": True,
                "design_doc": design_doc,
                "error": last_err,
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
                # 可选 LLM 摘要（不影响 pass/fail）
                _ = await _llm(ctx, QA_PROMPT, f"试玩通过\n{log_excerpt}")
                return {"qa_ok": True, "design_doc": design_doc, "qa_attempt": qa_attempt}

            if qa_attempt < settings.qa_max_retries:
                return {
                    "qa_ok": False,
                    "qa_attempt": qa_attempt,
                    "qa_retry": True,
                    "playtest_errors": errors,
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
            await _pause_hitl(
                ctx,
                "qa_failed",
                design_doc,
                {"qa_report": errors, "console_logs": console_logs},
            )
            return {
                "qa_ok": False,
                "hitl_stop": True,
                "design_doc": design_doc,
                "qa_attempt": qa_attempt,
                "playtest_errors": errors,
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
    g.add_node("art", art_node)
    g.add_node("code", code_node)
    g.add_node("qa", qa_node)
    g.add_node("done", done_node)
    g.add_conditional_edges(
        START, route_start, {"plan": "plan", "art": "art", "code": "code"}
    )
    g.add_conditional_edges("plan", after_plan, {END: END})
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

    r: redis.Redis = ctx["redis"]
    async with dbmod.SessionLocal() as s:
        run = await s.get(GenerationRun, run_id)
        if run is None:
            return
        game = await s.get(Game, run.game_id)
        if game is None:
            return
        try:
            with observe_run(str(run_id)):
                await _run_body(s, r, run, game, run_id, resume, decision, modify_text)
        except Exception as e:
            run.status = RunStatus.FAILED.value
            run.ended_at = datetime.now(UTC)
            await s.commit()
            await publish_event(
                run_id,
                WSEventType.ERROR,
                {"code": "RUN_FAILED", "message": str(e), "fatal": True},
            )


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
    if resume:
        st = await ckpt.load_state(r, run_id) or {}
        design_doc = st.get("design_doc") or run.requirement
        run.status = RunStatus.RUNNING.value
        await s.commit()

    forge_ctx = _Ctx(s, r, run, game)
    graph = _build_graph(forge_ctx)
    initial: ForgeState = {
        "run_id": str(run_id),
        "resume": resume,
        "decision": decision,
        "modify_text": modify_text,
        "design_doc": design_doc,
    }
    await graph.ainvoke(initial)
