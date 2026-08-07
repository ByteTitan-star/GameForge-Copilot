"""LLM 配置端点（M2 真实逻辑）：CRUD + 连通测试，全部 me-scoped 需登录。"""

from uuid import UUID

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.core.response import ApiResponse, ErrorResponse
from app.enums import LLMProvider
from app.llm import services
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigCreateResp,
    LLMConfigDeleteResp,
    LLMConfigDryTestResp,
    LLMConfigPatch,
    LLMConfigResp,
    LLMConfigTestReq,
    LLMConfigTestResp,
)

router = APIRouter(prefix="/me/llm-configs", tags=["llm-config"])

ERR_404 = {404: {"model": ErrorResponse, "description": "配置不存在"}}
ERR_400 = {400: {"model": ErrorResponse, "description": "连通测试失败"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "删除默认配置需先指定新默认"}}


@router.get("", response_model=ApiResponse[list[LLMConfigResp]])
async def list_configs(user: CurrentUser, db: DbSession) -> ApiResponse[list[LLMConfigResp]]:
    return ApiResponse(data=await services.list_configs(db, user))


@router.get("/models", response_model=ApiResponse[list[str]])
async def list_models(
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
    provider: LLMProvider = LLMProvider.ANTHROPIC,
) -> ApiResponse[list[str]]:
    """按 provider 拉可选模型（用户配置 key；失败回退白名单，docs/05）。"""
    return ApiResponse(data=await services.list_models_for_user(db, r, user, provider))


@router.post(
    "",
    response_model=ApiResponse[LLMConfigCreateResp],
    status_code=201,
    responses=ERR_400,
)
async def create_config(
    user: CurrentUser, db: DbSession, req: LLMConfigCreate
) -> ApiResponse[LLMConfigCreateResp]:
    return ApiResponse(data=await services.create_config(db, user, req))


@router.post(
    "/test",
    response_model=ApiResponse[LLMConfigDryTestResp],
)
async def test_draft_config(
    _user: CurrentUser, req: LLMConfigTestReq
) -> ApiResponse[LLMConfigDryTestResp]:
    """保存前连通测试（provider + model + apikey + base_url），不落库。"""
    return ApiResponse(data=await services.test_draft_config(req))


@router.patch("/{config_id}", response_model=ApiResponse[LLMConfigResp], responses=ERR_404)
async def patch_config(
    user: CurrentUser, db: DbSession, config_id: UUID, req: LLMConfigPatch
) -> ApiResponse[LLMConfigResp]:
    return ApiResponse(data=await services.patch_config(db, user, config_id, req))


@router.delete(
    "/{config_id}",
    response_model=ApiResponse[LLMConfigDeleteResp],
    responses={**ERR_404, **ERR_409},
)
async def delete_config(
    user: CurrentUser, db: DbSession, config_id: UUID
) -> ApiResponse[LLMConfigDeleteResp]:
    return ApiResponse(data=await services.delete_config(db, user, config_id))


@router.post(
    "/{config_id}/test",
    response_model=ApiResponse[LLMConfigTestResp],
    responses=ERR_404,
)
async def test_config(
    user: CurrentUser, db: DbSession, config_id: UUID
) -> ApiResponse[LLMConfigTestResp]:
    return ApiResponse(data=await services.test_config(db, user, config_id))
