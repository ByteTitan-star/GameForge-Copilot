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
from app.enums import LLMProvider, RunPhase, RunStatus, WSEventType
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

# 保留 title/gameplay/controls/levels 四个旧字段，避免现有前端展示和历史数据失效；
# 更完整的设计信息放在新增字段中，由开发和 QA 阶段共同消费。
DESIGN_DOC_SCHEMA = r"""
{
  "schema_version": "2.0",
  "title": "游戏名称",
  "gameplay": "用一段话说明核心玩法、玩家目标与完整游戏循环",
  "controls": ["面向玩家的操作说明，例如：A/D 或方向键左右移动"],
  "levels": ["关卡名称或阶段名称，顺序与 level_specs 保持一致"],
  "overview": {
    "genre": "游戏类型",
    "target_experience": "希望玩家获得的核心体验",
    "session_length": "预计单局时长",
    "scope": "适合单个离线 index.html 实现的原型范围",
    "assumptions": ["当原需求缺少非关键细节时采用的最小合理假设"]
  },
  "core_loop": ["按实际游玩顺序描述可重复的玩家行为与系统反馈"],
  "rules": {
    "objectives": ["明确、可观察的玩家目标"],
    "win_conditions": ["胜利条件"],
    "lose_conditions": ["失败条件"],
    "scoring": ["计分、奖励或评价规则"],
    "progression": ["关卡推进、能力或难度成长规则"]
  },
  "game_states": [
    {
      "id": "menu",
      "purpose": "该状态的作用",
      "enter_actions": ["进入状态时发生的行为"],
      "available_actions": ["玩家在该状态可执行的操作"],
      "transitions": ["触发条件 -> 目标状态"]
    }
  ],
  "entities": [
    {
      "id": "稳定且唯一的英文标识",
      "name": "显示名称",
      "type": "player/enemy/obstacle/collectible/projectile/environment",
      "behavior": ["运行规则"],
      "properties": {"关键属性": "明确的初始值或取值范围"}
    }
  ],
  "level_specs": [
    {
      "id": "level_1",
      "name": "关卡名称",
      "goal": "本关目标",
      "setup": ["初始布局、实体和数值"],
      "mechanics": ["本关启用的机制"],
      "difficulty": ["难度参数及变化方式"],
      "completion": "完成判定",
      "next": "下一关 id；最后一关填写 victory"
    }
  ],
  "ui": {
    "screens": ["至少包含主菜单、游戏界面、暂停、失败、通关界面"],
    "hud": ["分数、生命、进度等实时信息及显示条件"],
    "feedback": ["命中、受伤、得分、失败、通关等视听反馈"],
    "instructions": ["首次进入即可理解的玩法与操作提示"]
  },
  "presentation": {
    "visual_style": "可由 CSS、Canvas 与已提供素材实现的统一风格",
    "color_palette": ["#RRGGBB"],
    "asset_needs": [
      {
        "id": "素材用途标识",
        "kind": "sprite/background/effect/ui/audio",
        "purpose": "使用位置",
        "fallback": "素材不可用时的程序化替代方案"
      }
    ],
    "effects": ["关键动画、粒子、镜头或声音反馈"]
  },
  "technical_constraints": [
    "单个 index.html、离线运行、无外部依赖、无网络请求",
    "同时支持键盘和触控操作",
    "画面随视口自适应且核心玩法区域保持可见"
  ],
  "acceptance_criteria": [
    {
      "id": "AC-01",
      "requirement": "一个可从玩家视角观察的完整功能要求",
      "verification": "自动试玩或人工试玩可执行的验证步骤"
    }
  ]
}
""".strip()

PLAN_PROMPT = f"""
你是一名资深游戏玩法与系统策划，负责把用户的自然语言需求转化为可直接交给
HTML5 游戏工程师实现的结构化设计稿。你的目标不是复述创意，而是补齐一个
“可开始、可游玩、可暂停、可失败、可通关、可重新开始”的完整可试玩原型闭环。

工作原则：
1. 忠实保留用户明确提出的主题、机制、角色、规则和限制，不擅自改变核心创意。
2. 对非关键缺失信息采用最小且可实现的合理假设，并写入 overview.assumptions；
   如果不同解释会改变核心玩法，则选择最贴近原需求且最适合单页原型的一种。
3. 控制范围，使全部内容能在单个离线 index.html 中稳定实现；不要设计服务器、
   联机、登录、支付或必须依赖外部资源的功能。
4. 至少设计主菜单、游戏中、暂停、关卡完成或过渡、失败、最终通关状态，以及
   从失败/通关重新开始的路径；对应 game_states.id 必须包含 menu、playing、
   paused、level_complete、game_over、victory。
5. levels 与 level_specs 必须对应。若用户未指定关卡数量，设计 3 个短关卡或
   3 个清晰递进阶段；每一关引入或强化一个变化，不能只修改名称。
6. controls 必须是玩家看得懂的操作说明；game_states、entities、level_specs 和
   acceptance_criteria 必须具体到工程师无需再次猜测。
7. 每一条验收标准都必须可观察、可复现，并覆盖启动、核心操作、关卡推进、
   胜负、重开、键盘、触控和控制台无致命错误。

输出要求：
- 只输出一个合法 JSON 对象，不输出 Markdown、代码围栏、说明或前后缀。
- 严格使用下面的字段结构，不缺字段，不新增同义字段。
- 所有数组即使只有一项也必须保持数组类型；所有 id 使用稳定的英文 snake_case。
- 不允许出现“待定”“自行发挥”“等”“参考常规做法”这类无法实现或验收的表述。

设计稿 JSON 结构：
{DESIGN_DOC_SCHEMA}
""".strip()

PLAN_REVISE_PROMPT = f"""
你是一名资深游戏玩法与系统策划，负责根据用户修改意见修订一份已经结构化的
游戏设计稿。你必须返回完整的新版本，而不是补丁、差异说明或修改建议。

修订规则：
1. 用户最新修改意见优先于旧设计稿；未被修改意见影响的内容应保持稳定。
2. 识别修改对规则、状态、实体、关卡、UI、操作和验收标准造成的连锁影响，
   同步更新所有相关字段，避免前后矛盾。
3. 仍须保证主菜单—游玩—暂停—失败/通关—重开的完整闭环，并保持单个离线
   index.html 可实现。
4. 保留 title/gameplay/controls/levels 四个兼容字段，并保证它们与详细字段一致。
5. 新增的非关键假设写入 overview.assumptions，不得把用户明确要求降级为假设。

输出要求：只输出一个符合下列结构的合法 JSON 对象，不输出 Markdown、代码围栏、
解释、差异列表或任何前后缀。

设计稿 JSON 结构：
{DESIGN_DOC_SCHEMA}
""".strip()

CODE_PROMPT = f"""
你是一名资深 HTML5 游戏工程师。请根据已经由用户确认的设计稿，交付一个完整、
可试玩、离线运行的小游戏，而不是静态展示页、机制片段或带占位符的 Demo。

硬性约束：
1. 只生成一个自包含的 index.html；CSS 与 JavaScript 全部内联。
2. 禁止外部依赖、CDN、网络请求、动态 import、服务端接口和本地额外文件引用。
3. 只使用输入中明确提供的数据 URI 素材；未提供或加载失败的素材必须使用
   Canvas/CSS 程序化图形作为可靠回退，不能阻止游戏开始。
4. 必须实现设计稿中的主菜单、说明、游戏中、暂停、关卡过渡、失败、最终通关、
   重新开始，以及清晰的 HUD 和即时反馈。
5. 键盘和触控都必须可操作；按钮具备足够点击区域；页面缩放后核心游戏区域、
   HUD 和关键按钮仍可见。
6. 游戏循环使用 requestAnimationFrame，并限制异常大的 delta time；切换状态、
   重开或重进关卡时必须正确重置计时器、输入、实体和临时效果。
7. 不得留下 TODO、伪代码、未实现按钮、仅在注释中描述的功能或依赖刷新页面的重开。
8. 不得通过删除关卡、敌人、碰撞、胜负或反馈等功能来规避实现难点。
9. 正常游玩路径不得产生未捕获异常、无限循环或持续刷新的控制台错误。

实现优先级：先确保完整状态闭环和核心玩法正确，再完成关卡递进、反馈和视觉润色。
输出前在内部逐项核对设计稿的 acceptance_criteria 和下方试玩规范，但不要输出核对过程。

工程约定：
{_CONV}

自动试玩规范：
{_PLAYTEST}

输出要求：只输出完整 HTML 源码，第一个非空字符必须属于 <!DOCTYPE html>，
最后必须以 </html> 结束；不要输出 Markdown 代码围栏、解释或文件名。
""".strip()

CODE_REPAIR_PROMPT = f"""
你是一名资深 HTML5 游戏故障修复工程师。输入会包含已确认设计稿、自动试玩错误、
QA 根因分析以及当前完整 HTML。请在当前实现基础上修复根因，并返回可直接替换的
完整 index.html。

修复规则：
1. 优先做范围清晰的根因修复，保留当前已经正常工作的玩法、视觉、关卡和交互。
2. 同时检查修复对菜单、暂停、关卡切换、失败、通关、重开、键盘和触控的回归影响。
3. 如果错误暴露出设计稿中的必需功能尚未实现，必须补齐该功能，而不是绕过检测。
4. 不得隐藏错误、吞掉所有异常、伪造通过结果，或删除碰撞、实体、关卡、胜负条件。
5. 当前 HTML 即使结构不佳，也必须输出一份语法完整、可独立运行的新 HTML；
   不得只返回 diff、代码片段、说明或修复步骤。
6. 继续遵守单文件、离线、无外部依赖、无网络请求和素材回退要求。
7. 当前 HTML 中形如 __FORGE_DATA_URI_0000__ 的字符串代表已存在素材，必须按原样
   保留这些占位符；运行时会在构建前还原真实 data URI。

工程约定：
{_CONV}

自动试玩规范：
{_PLAYTEST}

输出要求：只输出完整 HTML 源码，以 <!DOCTYPE html> 开始并以 </html> 结束，
不要输出 Markdown 代码围栏或任何解释。
""".strip()

QA_PROMPT = f"""
你是一名 HTML5 游戏 QA 负责人。自动试玩已经判定本次构建失败。请结合已确认设计稿、
错误列表和控制台日志进行根因分析，为修复工程师提供可执行且有优先级的诊断。

诊断原则：
1. 区分根因与连带症状，优先定位会阻止启动、操作、状态切换或胜负闭环的 P0 问题。
2. 每项修复建议都必须描述“哪里有问题、应怎样修改、修复后如何验证”。
3. 不要建议删除功能、放宽验收条件、隐藏异常或伪造测试状态。
4. 覆盖与本次改动相关的回归检查，尤其是菜单、暂停、关卡推进、失败、通关、重开、
   键盘、触控和控制台错误。
5. 不编造日志中不存在的事实；证据不足时明确写出最可能原因和需要验证的点。

自动试玩规范：
{_PLAYTEST}

只输出一个合法 JSON 对象，不要输出 Markdown 或解释，结构如下：
{{
  "summary": "失败现象与最可能根因的简要结论",
  "root_causes": ["按优先级排列的根因"],
  "required_fixes": [
    {{
      "priority": "P0/P1/P2",
      "location": "建议检查的函数、状态或模块",
      "change": "可直接执行的修改要求",
      "expected_result": "修复后的可观察结果"
    }}
  ],
  "regression_checks": ["修复后必须重新验证的具体步骤"]
}}
""".strip()

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
