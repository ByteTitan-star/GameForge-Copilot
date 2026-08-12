"""发布审批端点（M7 真实逻辑）：submit(owner) + queue/approve/reject/take_down(admin)。

状态机 docs/04；admin 操作落审计。
"""

from uuid import UUID

from fastapi import APIRouter

from app.auth.deps import AdminUser, CurrentUser, DbSession
from app.core.response import ApiResponse, ErrorResponse
from app.enums import GameStatus, PublishStatus
from app.publish import services
from app.schemas.publish import (
    GameRef,
    PublishApproveResp,
    PublishQueueItem,
    PublishRejectReq,
    PublishRejectResp,
    PublishSubmitReq,
    PublishSubmitResp,
    TakeDownReq,
    TakeDownResp,
)

router = APIRouter(tags=["publish"])

ERR_404 = {404: {"model": ErrorResponse, "description": "游戏或申请不存在"}}
ERR_403 = {403: {"model": ErrorResponse, "description": "无权限"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "状态冲突"}}


@router.post(
    "/games/{game_id}/publish/submit",
    response_model=ApiResponse[PublishSubmitResp],
    responses={**ERR_404, **ERR_409},
)
async def submit_publish(
    game_id: UUID, req: PublishSubmitReq, user: CurrentUser, db: DbSession
) -> ApiResponse[PublishSubmitResp]:
    pr = await services.submit(db, user, game_id, req.version, req.note)
    return ApiResponse(
        data=PublishSubmitResp(
            publish_request_id=pr.id,
            status=PublishStatus(pr.status),
            game_id=pr.game_id,
            version=pr.version,
        )
    )


@router.get("/publish/queue", response_model=ApiResponse[list[PublishQueueItem]])
async def publish_queue(
    admin: AdminUser, db: DbSession, status: PublishStatus | None = None
) -> ApiResponse[list[PublishQueueItem]]:
    rows = await services.list_queue(db, status)
    return ApiResponse(
        data=[
            PublishQueueItem(
                publish_request_id=req.id,
                game_id=game.id,
                game_title=game.title,
                version=req.version,
                status=PublishStatus(req.status),
                created_at=req.created_at,
            )
            for req, game in rows
        ]
    )


@router.post("/publish/{publish_request_id}/approve", responses={**ERR_404, **ERR_409})
async def approve_publish(
    publish_request_id: UUID, admin: AdminUser, db: DbSession
) -> ApiResponse[PublishApproveResp]:
    req, game = await services.approve(db, admin, publish_request_id)
    return ApiResponse(
        data=PublishApproveResp(
            publish_request_id=req.id,
            status=PublishStatus(req.status),
            game=GameRef(game_id=game.id, slug=game.slug, status=GameStatus(game.status)),
        )
    )


@router.post(
    "/publish/{publish_request_id}/reject",
    response_model=ApiResponse[PublishRejectResp],
    responses={**ERR_404, **ERR_409},
)
async def reject_publish(
    publish_request_id: UUID, req: PublishRejectReq, admin: AdminUser, db: DbSession
) -> ApiResponse[PublishRejectResp]:
    pr, game = await services.reject(db, admin, publish_request_id, req.reason)
    return ApiResponse(
        data=PublishRejectResp(
            publish_request_id=pr.id,
            status=PublishStatus(pr.status),
            game=GameRef(game_id=game.id, slug=game.slug, status=GameStatus(game.status)),
        )
    )


@router.post(
    "/publish/{publish_request_id}/withdraw",
    response_model=ApiResponse[PublishSubmitResp],
    responses={**ERR_404, **ERR_409},
)
async def withdraw_publish(
    publish_request_id: UUID, user: CurrentUser, db: DbSession
) -> ApiResponse[PublishSubmitResp]:
    """owner 撤回自己的发布申请（submitted/reviewing → withdrawn，游戏回 draft）。"""
    pr = await services.withdraw(db, user, publish_request_id)
    return ApiResponse(
        data=PublishSubmitResp(
            publish_request_id=pr.id,
            status=PublishStatus(pr.status),
            game_id=pr.game_id,
            version=pr.version,
        )
    )


@router.post(
    "/games/{game_id}/take-down",
    response_model=ApiResponse[TakeDownResp],
    responses={**ERR_404, **ERR_409},
)
async def take_down(
    game_id: UUID, req: TakeDownReq, admin: AdminUser, db: DbSession
) -> ApiResponse[TakeDownResp]:
    game = await services.take_down(db, admin, game_id, req.reason)
    return ApiResponse(
        data=TakeDownResp(game_id=game.id, status=GameStatus(game.status), reason=req.reason)
    )
