"""run 端点（M4/M6 真实逻辑）：发起 run / 列表 / 状态 / HITL resolve。

路径 game-scoped 与 run-scoped 混合，均 owner 过滤。执行见 app.forge.graph。
"""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse, ErrorResponse
from app.enums import EntryPhase, PauseReason, RunPhase, RunStatus
from app.forge import state as ckpt
from app.forge.event_log import list_events
from app.forge.messages import add_message, list_messages, stable_payload_key
from app.forge.queue import enqueue_resume
from app.forge.reliability.pause import pause_reason_from_state, recovery_from_state
from app.games import services
from app.models.generation_run import GenerationRun
from app.schemas.active_run import ActiveRunItem
from app.schemas.forge_message import ForgeMessageItem
from app.schemas.run import (
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

ERR_404 = {404: {"model": ErrorResponse, "description": "run 或游戏不存在或不可见"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "邮箱未验证"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "状态冲突"}}
ERR_429 = {429: {"model": ErrorResponse, "description": "配额耗尽"}}

_WS = "/ws/runs/{run_id}"


def _to_resp(run: GenerationRun) -> RunResp:
    return RunResp(
        run_id=run.id,
        game_id=run.game_id,
        status=RunStatus(run.status),
        phase=RunPhase(run.phase),
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
    rows = await services.list_runs(db, user, game_id)
    return ApiResponse(
        data=[
            RunListItem(
                run_id=run.id,
                status=RunStatus(run.status),
                phase=RunPhase(run.phase),
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
    await services.get_owned_game(db, user, game_id)
    rows = await list_messages(db, game_id, limit=limit, before=before)
    return ApiResponse(
        data=[
            ForgeMessageItem(
                message_id=row.id,
                game_id=row.game_id,
                run_id=row.run_id,
                role=row.role,
                kind=row.kind,
                content=row.content,
                metadata=row.metadata_json,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


_HITL_PHASES = {"plan_confirm", "art_confirm", "sandbox_failed", "qa_failed"}


def _hitl_from_state(
    run: GenerationRun, state: dict | None
) -> tuple[HitlState | None, HitlWaitDetail | None]:
    # checkpoint 只描述“曾停在哪里”；run.status=paused 才表示当前仍可交互。
    # 任务已推进/结束时即使缓存残留，也不能向前端暴露可点击的 HITL 卡。
    if not state or run.status != RunStatus.PAUSED.value:
        return None, None
    phase = state.get("phase")
    if phase not in _HITL_PHASES:
        return None, None
    current = HitlState(node=str(phase))
    detail = HitlWaitDetail(
        node=str(phase),
        design_doc=state.get("design_doc"),
        action_url=f"/api/v1/games/{run.game_id}/runs/{run.id}/hitl/resolve",
        art_options=state.get("art_options"),
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
                phase=RunPhase(run.phase),
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
    run = await services.get_run(db, user, run_id)
    state = await ckpt.load_state(r, run_id, db)
    current_hitl, hitl_wait = _hitl_from_state(run, state)
    pause_reason = None
    recovery = None
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
            phase=RunPhase(run.phase),
            entry_phase=EntryPhase(getattr(run, "entry_phase", "plan") or "plan"),
            ws_url=_WS.format(run_id=run.id),
            current_hitl=current_hitl,
            hitl_wait=hitl_wait,
            pause_reason=pause_reason,
            recovery=recovery,
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
    run = await services.pause_run(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id, status=RunStatus(run.status), phase=RunPhase(run.phase)
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
    run = await services.resume_run_control(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id, status=RunStatus.RUNNING, phase=RunPhase(run.phase)
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
    run = await services.cancel_run(db, r, user, run_id)
    return ApiResponse(
        data=RunControlResp(
            run_id=run.id, status=RunStatus(run.status), phase=RunPhase(run.phase)
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
            run_id=run.id, status=RunStatus.RUNNING, phase=RunPhase(run.phase)
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
    if not await r.set(f"run:hitl:{run_id}", "1", nx=True, ex=60):
        raise AppError(ErrorCode.INVALID_STATE, "run 正在处理或已处理")
    state = await ckpt.load_state(r, run_id, db)
    if (
        state is None
        or state.get("phase") not in _HITL_PHASES
        or state.get("phase") != req.node
    ):
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "run 不在 HITL 等待态")
    if state.get("pause_reason") == PauseReason.RECOVERABLE_ERROR.value:
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(
            ErrorCode.INVALID_STATE,
            "可恢复故障请使用 /retry，而非 HITL resolve",
        )
    if run.status != RunStatus.PAUSED.value:
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "run 已结束")
    allowed_decisions = {
        "plan_confirm": {"approve", "modify"},
        "art_confirm": {"select_a", "select_b", "modify"},
        "sandbox_failed": {"approve", "modify"},
        "qa_failed": {"approve", "modify"},
    }
    if req.decision not in allowed_decisions[state["phase"]]:
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "当前 HITL 节点不支持该决策")
    if req.decision == "modify" and not (req.modify_text or "").strip():
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "修改意见不能为空")
    run.status = RunStatus.RUNNING.value
    run.ended_at = None
    selected_label = {"select_a": "已选择美术方案 A", "select_b": "已选择美术方案 B"}
    decision_text = (
        req.modify_text.strip()
        if req.modify_text
        else selected_label.get(req.decision, "已确认设计方案")
    )
    await add_message(
        db,
        game_id=run.game_id,
        run_id=run.id,
        user_id=user.id,
        role="user",
        kind="hitl_modify" if req.decision == "modify" else "hitl_approve",
        content=decision_text,
        metadata={"node": req.node, "decision": req.decision},
        dedupe_key=stable_payload_key(
            run.id,
            f"hitl:{req.node}:{req.decision}",
            {"design_doc": state.get("design_doc"), "content": decision_text},
        ),
    )
    await enqueue_resume(db, r, run_id, req.decision, req.modify_text)
    await db.commit()
    # 锁只覆盖一次 resolve 的并发窗口；下一阶段可能立即出现新的合法 HITL。
    await r.delete(f"run:hitl:{run_id}")
    next_phase = (
        RunPhase.ART
        if state.get("phase") in {"plan_confirm", "art_confirm"}
        else RunPhase.CODE
    )
    return ApiResponse(
        data=HitlResolveResp(run_id=run.id, status=RunStatus.RUNNING, phase=next_phase)
    )
