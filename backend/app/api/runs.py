"""run 端点（M4/M6 真实逻辑）：发起 run / 列表 / 状态 / HITL resolve。

路径 game-scoped 与 run-scoped 混合，均 owner 过滤。执行见 app.forge.graph。
"""

from uuid import UUID

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse, ErrorResponse
from app.enums import EntryPhase, RunPhase, RunStatus
from app.forge import queue as forge_queue
from app.forge import state as ckpt
from app.forge.event_log import list_events
from app.games import services
from app.models.generation_run import GenerationRun
from app.schemas.active_run import ActiveRunItem
from app.schemas.run import (
    HitlResolveReq,
    HitlResolveResp,
    HitlState,
    HitlWaitDetail,
    RunControlResp,
    RunCreate,
    RunListItem,
    RunResp,
    RunStatusResp,
)
from app.schemas.ws import WSEvent

router = APIRouter(tags=["runs"])

ERR_404 = {404: {"model": ErrorResponse, "description": "run 或游戏不存在或不可见"}}
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
    responses={**ERR_404, **ERR_429},
)
async def create_run(
    game_id: UUID, req: RunCreate, user: CurrentUser, db: DbSession, r: RedisClient
) -> ApiResponse[RunResp]:
    run = await services.create_run(db, r, user, game_id, req)
    return ApiResponse(data=_to_resp(run))


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


_HITL_PHASES = {"plan_confirm", "sandbox_failed", "qa_failed"}


def _hitl_from_state(
    run: GenerationRun, state: dict | None
) -> tuple[HitlState | None, HitlWaitDetail | None]:
    if not state:
        return None, None
    phase = state.get("phase")
    if phase not in _HITL_PHASES:
        return None, None
    current = HitlState(node=str(phase))
    detail = HitlWaitDetail(
        node=str(phase),
        design_doc=state.get("design_doc"),
        action_url=f"/api/v1/games/{run.game_id}/runs/{run.id}/hitl/resolve",
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
    state = await ckpt.load_state(r, run_id)
    current_hitl, hitl_wait = _hitl_from_state(run, state)
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
    """解决 HITL：plan_confirm / sandbox_failed / qa_failed → enqueue resume。"""
    _ = game_id
    run = await services.get_run(db, user, run_id)
    if not await r.set(f"run:hitl:{run_id}", "1", nx=True, ex=3600):
        raise AppError(ErrorCode.INVALID_STATE, "run 正在处理或已处理")
    state = await ckpt.load_state(r, run_id)
    if state is None or state.get("phase") not in _HITL_PHASES:
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "run 不在 HITL 等待态")
    if run.status not in (RunStatus.RUNNING.value, RunStatus.PAUSED.value):
        await r.delete(f"run:hitl:{run_id}")
        raise AppError(ErrorCode.INVALID_STATE, "run 已结束")
    run.status = RunStatus.RUNNING.value
    await db.commit()
    await forge_queue.enqueue_resume(run_id, req.decision, req.modify_text)
    next_phase = RunPhase.ART if state.get("phase") == "plan_confirm" else RunPhase.CODE
    return ApiResponse(
        data=HitlResolveResp(run_id=run.id, status=RunStatus.RUNNING, phase=next_phase)
    )
