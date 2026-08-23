"""run 端点（M4/M6 真实逻辑）：发起 run / 列表 / 状态 / HITL resolve。

路径 game-scoped 与 run-scoped 混合，均 owner 过滤。执行见 app.forge.graph。
"""

from typing import Any, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import update

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse, ErrorResponse
from app.enums import EntryPhase, PauseReason, RunCommandType, RunPhase, RunStatus
from app.forge import state as ckpt
from app.forge.commands import legacy_decision_for, normalize_resume_command
from app.forge.event_log import list_events
from app.forge.hitl import allowed_commands_for, allowed_decisions_for, is_hitl_phase
from app.forge.messages import add_message, list_messages, stable_payload_key
from app.forge.queue import enqueue_resume
from app.forge.reliability.pause import pause_reason_from_state, recovery_from_state
from app.games import services
from app.models.generation_run import GenerationRun
from app.schemas.active_run import ActiveRunItem
from app.schemas.forge_message import ForgeMessageItem
from app.schemas.run import (
    ArtifactGateDetail,
    HitlResolveReq,
    HitlResolveResp,
    HitlState,
    HitlWaitDetail,
    RecoveryDetail,
    RunControlResp,
    RunCreate,
    RunListItem,
    RunResp,
    RunStatusResp,
)
from app.schemas.ws import WSEvent

router = APIRouter(tags=["runs"])

ERR_404: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "run 或游戏不存在或不可见"}
}
ERR_403: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "邮箱未验证"}
}
ERR_409: dict[int | str, dict[str, Any]] = {
    409: {"model": ErrorResponse, "description": "状态冲突"}
}
ERR_429: dict[int | str, dict[str, Any]] = {
    429: {"model": ErrorResponse, "description": "配额耗尽"}
}

_WS = "/ws/runs/{run_id}"


def _to_resp(run: GenerationRun) -> RunResp:
    """将 GenerationRun ORM 转为 API 响应模型。

    作用：字段映射、枚举转换并附带 ws_url。
    场景：create_run 等端点返回体。
    参数：run — GenerationRun ORM 实例。
    返回：RunResp。
    """
    return RunResp(
        run_id=run.id,
        game_id=run.game_id,
        status=RunStatus(run.status),
        phase=RunPhase(run.phase or RunPhase.PLAN.value),
        entry_phase=EntryPhase(getattr(run, "entry_phase", "plan") or "plan"),
        ws_url=_WS.format(run_id=run.id),
    )


@router.post(
    "/games/{game_id}/runs",
    response_model=ApiResponse[RunResp],
    status_code=201,
    responses={**ERR_404, **ERR_403, **ERR_429},
)
async def create_run(
    game_id: UUID,
    req: RunCreate,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[RunResp]:
    """为游戏创建并入队生成 run。

    作用：支持 Idempotency-Key 防重复提交。
    场景：POST /games/{game_id}/runs。
    参数：game_id — 游戏 ID；req — 创建请求；request/user/db/r — 依赖。
    返回：ApiResponse[RunResp]。
    """
    # Idempotency-Key（可选）：同一 key 在 TTL 窗口内复用首次创建的 run，
    # 吸收客户端网络重试/双击，避免重复入队烧 LLM token。
    idem_key = (request.headers.get("Idempotency-Key") or "").strip()
    if idem_key:
        cached = await r.get(f"idem:run:{user.id}:{idem_key}")
        if cached:
            return ApiResponse(data=RunResp.model_validate_json(cached))
    run = await services.create_run(db, r, user, game_id, req, idem_key or None)
    resp = _to_resp(run)
    if idem_key:
        await r.setex(
            f"idem:run:{user.id}:{idem_key}",
            settings.create_run_idempotency_ttl,
            resp.model_dump_json(),
        )
    return ApiResponse(data=resp)


@router.get(
    "/games/{game_id}/runs",
    response_model=ApiResponse[list[RunListItem]],
    responses=ERR_404,
)
async def list_runs(
    game_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[list[RunListItem]]:
    """列出某游戏下的全部 run。

    作用：owner 校验后返回 run 摘要列表。
    场景：GET /games/{game_id}/runs。
    参数：game_id — 游戏 ID；user/db — 依赖。
    返回：ApiResponse[list[RunListItem]]。
    """
    rows = await services.list_runs(db, user, game_id)
    return ApiResponse(
        data=[
            RunListItem(
                run_id=run.id,
                status=RunStatus(run.status),
                phase=RunPhase(run.phase or RunPhase.PLAN.value),
                started_at=run.started_at,
                ended_at=run.ended_at,
            )
            for run in rows
        ]
    )


@router.get(
    "/games/{game_id}/messages",
    response_model=ApiResponse[list[ForgeMessageItem]],
    responses=ERR_404,
)
async def get_forge_messages(
    game_id: UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
    before: UUID | None = None,
) -> ApiResponse[list[ForgeMessageItem]]:
    """分页获取 Forge 对话消息历史。

    作用：owner 校验后拉取游戏消息流。
    场景：GET /games/{game_id}/messages。
    参数：game_id — 游戏 ID；limit/before — 分页；user/db — 依赖。
    返回：ApiResponse[list[ForgeMessageItem]]。
    """
    await services.get_owned_game(db, user, game_id)
    rows = await list_messages(db, game_id, limit=limit, before=before)
    return ApiResponse(
        data=[
            ForgeMessageItem(
                message_id=row.id,
                game_id=row.game_id,
                run_id=row.run_id,
                role=cast(Literal["user", "assistant", "system"], row.role),
                kind=row.kind,
                content=row.content,
                metadata=row.metadata_json,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


def _hitl_from_state(
    run: GenerationRun, state: dict | None
) -> tuple[HitlState | None, HitlWaitDetail | None]:
    """从检查点解析 HITL 等待态。

    作用：仅在 run 为 paused 且 phase 为 HITL 节点时返回交互信息。
    场景：get_run 组装 hitl_wait 字段。
    参数：run — GenerationRun；state — Redis 检查点字典。
    返回：(HitlState | None, HitlWaitDetail | None)。
    """
    # checkpoint 只描述“曾停在哪里”；run.status=paused 才表示当前仍可交互。
    # 任务已推进/结束时即使缓存残留，也不能向前端暴露可点击的 HITL 卡。
    if not state or run.status != RunStatus.PAUSED.value:
        return None, None
    phase = state.get("phase")
    if not is_hitl_phase(str(phase) if phase is not None else None):
        return None, None
    current = HitlState(node=str(phase))
    failure = state.get("failure")
    fc = failure.get("failure_class") if isinstance(failure, dict) else None
    detail = HitlWaitDetail(
        node=str(phase),
        design_doc=state.get("design_doc"),
        action_url=f"/api/v1/games/{run.game_id}/runs/{run.id}/hitl/resolve",
        art_options=state.get("art_options"),
        allowed_commands=list(allowed_commands_for(str(phase), str(fc) if fc else None)),
        control_revision=int(run.control_revision or 0),
        failure=failure if isinstance(failure, dict) else None,
    )
    return current, detail


@router.get("/me/runs/active", response_model=ApiResponse[list[ActiveRunItem]])
async def list_active_runs(user: CurrentUser, db: DbSession) -> ApiResponse[list[ActiveRunItem]]:
    """跨游戏进行中的 run，供刷新/跳转后找回任务。"""
    rows = await services.list_user_active_runs(db, user)
    return ApiResponse(
        data=[
            ActiveRunItem(
                run_id=run.id,
                game_id=run.game_id,
                game_title=game.title,
                status=RunStatus(run.status),
                phase=RunPhase(run.phase or RunPhase.PLAN.value),
                entry_phase=EntryPhase(getattr(run, "entry_phase", "plan") or "plan"),
                started_at=run.started_at,
                ws_url=_WS.format(run_id=run.id),
            )
            for run, game in rows
        ]
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[RunStatusResp], responses=ERR_404)
async def get_run(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunStatusResp]:
    """获取 run 完整状态（含 HITL、暂停与产物门禁）。

    作用：联查 DB 行与 Redis 检查点组装 RunStatusResp。
    场景：GET /runs/{run_id}。
    参数：run_id — run ID；user/db/r — 依赖。
    返回：ApiResponse[RunStatusResp]。
    """
    run = await services.get_run(db, user, run_id)
    state = await ckpt.load_state(r, run_id, db)
    current_hitl, hitl_wait = _hitl_from_state(run, state)
    pause_reason = None
    recovery = None
    artifact_gate = None
    if state and any(
        k in state for k in ("previewable", "publishable", "qa_ok", "generation_success")
    ):
        artifact_gate = ArtifactGateDetail(
            generation_success=bool(state.get("generation_success", False)),
            previewable=bool(state.get("previewable", False)),
            publishable=bool(state.get("publishable", False)),
            qa_ok=bool(state.get("qa_ok", False)),
        )
    if run.status == RunStatus.PAUSED.value:
        try:
            reason = pause_reason_from_state(state)
            pause_reason = reason.value if reason else None
        except ValueError:
            pause_reason = None
        raw_recovery = recovery_from_state(state)
        if raw_recovery:
            recovery = RecoveryDetail(
                node=str(raw_recovery.get("node") or ""),
                error_code=str(raw_recovery.get("error_code") or ""),
                attempts=int(raw_recovery.get("attempts") or 0),
                can_retry=bool(raw_recovery.get("can_retry", True)),
            )
    return ApiResponse(
        data=RunStatusResp(
            run_id=run.id,
            game_id=run.game_id,
            status=RunStatus(run.status),
            phase=RunPhase(run.phase or RunPhase.PLAN.value),
            entry_phase=EntryPhase(getattr(run, "entry_phase", "plan") or "plan"),
            ws_url=_WS.format(run_id=run.id),
            current_hitl=current_hitl,
            hitl_wait=hitl_wait,
            pause_reason=pause_reason,
            recovery=recovery,
            artifact_gate=artifact_gate,
        )
    )


@router.get("/runs/{run_id}/events", response_model=ApiResponse[list[WSEvent]], responses=ERR_404)
async def get_run_events(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[list[WSEvent]]:
    """WS 事件历史（Redis 缓冲），HTTP 回退 replay。"""
    await services.get_run(db, user, run_id)
    raw = await list_events(r, run_id)
    events = [WSEvent.model_validate_json(line) for line in raw]
    return ApiResponse(data=events)


@router.post(
    "/runs/{run_id}/pause",
    response_model=ApiResponse[RunControlResp],
    responses={**ERR_404, **ERR_409},
)
async def pause_run(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunControlResp]:
    """暂停进行中的 run。

    作用：委托 services.pause_run 并返回控制态。
    场景：POST /runs/{run_id}/pause。
    参数：run_id — run ID；user/db/r — 依赖。
    返回：ApiResponse[RunControlResp]。
    """
    run = await services.pause_run(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id,
            status=RunStatus(run.status),
            phase=RunPhase(run.phase or RunPhase.PLAN.value),
        )
    )


@router.post(
    "/runs/{run_id}/resume",
    response_model=ApiResponse[RunControlResp],
    responses={**ERR_404, **ERR_409},
)
async def resume_run(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunControlResp]:
    """从暂停态续跑 run。

    作用：委托 services.resume_run_control。
    场景：POST /runs/{run_id}/resume。
    参数：run_id — run ID；user/db/r — 依赖。
    返回：ApiResponse[RunControlResp]。
    """
    run = await services.resume_run_control(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id,
            status=RunStatus.RUNNING,
            phase=RunPhase(run.phase or RunPhase.PLAN.value),
        )
    )


@router.post(
    "/runs/{run_id}/cancel",
    response_model=ApiResponse[RunControlResp],
    responses={**ERR_404, **ERR_409},
)
async def cancel_run(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunControlResp]:
    """取消进行中的 run。

    作用：委托 services.cancel_run。
    场景：POST /runs/{run_id}/cancel。
    参数：run_id — run ID；user/db/r — 依赖。
    返回：ApiResponse[RunControlResp]。
    """
    run = await services.cancel_run(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id,
            status=RunStatus(run.status),
            phase=RunPhase(run.phase or RunPhase.PLAN.value),
        )
    )


@router.post(
    "/runs/{run_id}/retry",
    response_model=ApiResponse[RunControlResp],
    responses={**ERR_404, **ERR_409},
)
async def retry_run(
    run_id: UUID, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunControlResp]:
    """从失败阶段重试（Batch A · R3）。"""
    run = await services.retry_run(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id,
            status=RunStatus.RUNNING,
            phase=RunPhase(run.phase or RunPhase.PLAN.value),
        )
    )


@router.post(
    "/games/{game_id}/runs/{run_id}/hitl/resolve",
    response_model=ApiResponse[HitlResolveResp],
    responses={**ERR_404, **ERR_409},
)
async def resolve_hitl(
    game_id: UUID,
    run_id: UUID,
    req: HitlResolveReq,
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[HitlResolveResp]:
    """解决策划或美术 HITL，并把一次性恢复凭据写入队列。"""
    run = await services.get_run(db, user, run_id)
    if run.game_id != game_id:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏或 run 不存在")
    # TTL 收窄到 60s：仅用于拦截同一次 HITL 的并发双击；同一 run 后续 HITL 阶段
    # （如 plan_confirm→qa_failed）不会被遗留锁误阻塞。执行层的重复由 run:executing 兜底。
    lock_key = f"run:hitl:{run_id}"
    if not await r.set(lock_key, "1", nx=True, ex=60):
        raise AppError(ErrorCode.INVALID_STATE, "run 正在处理或已处理")
    try:
        state = await ckpt.load_state(r, run_id, db)
        phase = str(state.get("phase") or "") if state else ""
        if state is None or not is_hitl_phase(phase) or phase != req.node:
            raise AppError(ErrorCode.INVALID_STATE, "run 不在 HITL 等待态")
        if state.get("pause_reason") == PauseReason.RECOVERABLE_ERROR.value:
            raise AppError(
                ErrorCode.INVALID_STATE,
                "可恢复故障请使用 /retry，而非 HITL resolve",
            )
        if run.status != RunStatus.PAUSED.value:
            raise AppError(ErrorCode.INVALID_STATE, "run 已结束")

        command = (req.command or "").strip() or None
        decision = (req.decision or "").strip() or None
        if not command and not decision:
            raise AppError(ErrorCode.INVALID_STATE, "需要提供 decision 或 command")
        if command and command not in allowed_commands_for(phase):
            raise AppError(ErrorCode.INVALID_STATE, "当前 HITL 节点不支持该命令")
        if not command and decision not in allowed_decisions_for(phase):
            raise AppError(ErrorCode.INVALID_STATE, "当前 HITL 节点不支持该决策")

        mapped = normalize_resume_command(
            phase=phase, decision=decision or "", command=command, feedback=req.modify_text
        )
        decision_key = decision or legacy_decision_for(mapped.command_type)
        modify_text = req.modify_text
        if mapped.command_type is RunCommandType.CANCEL_RUN:
            cancelled = await services.cancel_run(db, r, user, run_id)
            return ApiResponse(
                data=HitlResolveResp(
                    run_id=cancelled.id,
                    status=RunStatus.FAILED,
                    phase=RunPhase(cancelled.phase or RunPhase.PLAN.value),
                )
            )
        if (
            decision_key == "modify"
            and mapped.command_type is not RunCommandType.REVISE_PLAN
            and not (modify_text or "").strip()
        ):
            raise AppError(ErrorCode.INVALID_STATE, "修改意见不能为空")
        if mapped.command_type is RunCommandType.REVISE_PLAN and not (modify_text or "").strip():
            modify_text = (
                "请根据失败报告修订策划，使玩法可实现且可验收。"
                if state.get("failure_report_id")
                else "请修订策划后重新确认。"
            )

        result = await db.execute(
            update(GenerationRun)
            .where(
                GenerationRun.id == run_id,
                GenerationRun.status == RunStatus.PAUSED.value,
            )
            .values(status=RunStatus.RUNNING.value, ended_at=None)
        )
        if int(getattr(result, "rowcount", 0) or 0) != 1:
            raise AppError(ErrorCode.INVALID_STATE, "run 已结束或不在 paused")
        run.status = RunStatus.RUNNING.value
        run.ended_at = None
        selected_label = {
            "select_a": "已选择美术方案 A",
            "select_b": "已选择美术方案 B",
            "approve": {
                "plan_confirm": "已确认设计方案",
                "art_confirm": "已确认美术方案",
                "sandbox_failed": "环境问题已处理，继续重试",
                "qa_failed": "已确认继续修复试玩问题",
            }.get(phase, "已确认，继续"),
            "modify": "已提交修改意见",
        }
        decision_text = (
            modify_text.strip()
            if modify_text and decision_key == "modify"
            else selected_label.get(decision_key, "已确认，继续")
        )
        await add_message(
            db,
            game_id=run.game_id,
            run_id=run.id,
            user_id=user.id,
            role="user",
            kind="hitl_modify" if decision_key == "modify" else "hitl_approve",
            content=decision_text,
            metadata={
                "node": req.node,
                "decision": decision_key,
                "command": mapped.command_type.value,
            },
            dedupe_key=stable_payload_key(
                run.id,
                f"hitl:{req.node}:{mapped.command_type.value}",
                {"design_doc": state.get("design_doc"), "content": decision_text},
            ),
        )
        await enqueue_resume(
            db,
            r,
            run_id,
            decision_key,
            modify_text,
            source="hitl",
            expected_control_revision=req.expected_control_revision,
            command=mapped.command_type.value,
        )
        await db.commit()
        if mapped.command_type is RunCommandType.REVISE_PLAN:
            next_phase = RunPhase.PLAN
        elif phase in {"plan_confirm", "art_confirm"}:
            next_phase = RunPhase.ART
        else:
            next_phase = RunPhase.CODE
        return ApiResponse(
            data=HitlResolveResp(run_id=run.id, status=RunStatus.RUNNING, phase=next_phase)
        )
    finally:
        await r.delete(lock_key)
