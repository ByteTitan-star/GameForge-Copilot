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
    """创作者提交游戏版本进入发布审核队列。

    作用：创建 PublishRequest 并将游戏状态置为 submitted。
    场景：游戏编辑页「提交发布」；游戏须为 draft/rejected/taken_down。
    参数：game_id — 游戏 ID；req — 版本与备注；user/db — 提交者与存储。
    返回：ApiResponse，data 为 PublishSubmitResp；状态冲突 409。
    """
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
    """列出发布审核队列（admin only）。

    作用：返回待审申请及关联游戏标题等信息。
    场景：管理后台发布审核台；可选 status 过滤。
    参数：admin — 管理员；db — 数据库会话；status — 可选 PublishStatus。
    返回：ApiResponse，data 为 PublishQueueItem 列表。
    """
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
    """管理员审批通过发布申请并上架游戏。

    作用：申请 approved、游戏 published、分配 slug、通知 owner。
    场景：POST /publish/{id}/approve。
    参数：publish_request_id — 申请 ID；admin/db — 审批人与存储。
    返回：ApiResponse，data 为 PublishApproveResp；不可审批 409。
    """
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
    """管理员驳回发布申请。

    作用：申请 rejected、游戏 rejected、记录理由并通知 owner。
    场景：POST /publish/{id}/reject。
    参数：publish_request_id — 申请 ID；req.reason — 驳回理由；admin/db — 审批人与存储。
    返回：ApiResponse，data 为 PublishRejectResp。
    """
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
    """owner 撤回自己的发布申请。

    作用：submitted/reviewing → withdrawn，游戏回 draft。
    场景：创作者在审核中撤回发布申请。
    参数：publish_request_id — 申请 ID；user/db — owner 与存储。
    返回：ApiResponse，data 为 PublishSubmitResp；不可撤回 409。
    """
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
    """管理员下架已发布游戏。

    作用：游戏状态 taken_down、记审计并通知 owner。
    场景：admin 手动下架或 scheduler 定时下架。
    参数：game_id — 游戏 ID；req.reason — 下架理由；admin/db — 操作者与存储。
    返回：ApiResponse，data 为 TakeDownResp；非 published 409。
    """
    game = await services.take_down(db, admin, game_id, req.reason)
    return ApiResponse(
        data=TakeDownResp(game_id=game.id, status=GameStatus(game.status), reason=req.reason)
    )
