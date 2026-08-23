"""LLM 配置端点（M2 真实逻辑）：CRUD + 连通测试，全部 me-scoped 需登录。"""

from uuid import UUID

from fastapi import APIRouter, Request

from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.auth.ratelimit import check_rate_limit
from app.core.config import settings
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
ERR_429 = {429: {"model": ErrorResponse, "description": "限流"}}


@router.get("", response_model=ApiResponse[list[LLMConfigResp]])
async def list_configs(user: CurrentUser, db: DbSession) -> ApiResponse[list[LLMConfigResp]]:
    """列出当前用户全部 LLM 配置。

    作用：返回已保存的 provider/model/base_url 等（apikey 脱敏）。
    场景：设置页 LLM 配置列表。
    参数：user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data 为 LLMConfigResp 列表。
    """
    return ApiResponse(data=await services.list_configs(db, user))


@router.get("/models", response_model=ApiResponse[list[str]])
async def list_models(
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
    provider: LLMProvider = LLMProvider.ANTHROPIC,
) -> ApiResponse[list[str]]:
    """按 provider 拉取可选模型列表。

    作用：调用用户配置的 key 请求 /models；失败回退内置白名单。
    场景：LLM 配置页模型下拉（docs/05）。
    参数：user — 当前用户；db/r — 存储；provider — LLM 提供商枚举。
    返回：ApiResponse，data 为模型 id 字符串列表。
    """
    return ApiResponse(data=await services.list_models_for_user(db, r, user, provider))


@router.post(
    "",
    response_model=ApiResponse[LLMConfigCreateResp],
    status_code=201,
    responses={**ERR_400, **ERR_429},
)
async def create_config(
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
    request: Request,
    req: LLMConfigCreate,
) -> ApiResponse[LLMConfigCreateResp]:
    """创建 LLM 配置（含连通性探测）。

    作用：保存前发最小 completion 验证配置，成功则落库。
    场景：设置页新增 LLM 配置；按用户限流防成本放大。
    参数：user/db/r — 用户与存储；req — 配置创建体。
    返回：ApiResponse，data 为 LLMConfigCreateResp；探测失败 400，限流 429。
    """
    # create 内含一次真实 LLM 连通探测，按用户限流防成本放大
    await check_rate_limit(
        r,
        f"rl:llm-probe:{user.id}",
        settings.llm_probe_rate_limit_per_min,
        60,
    )
    return ApiResponse(data=await services.create_config(db, user, req))


@router.post(
    "/test",
    response_model=ApiResponse[LLMConfigDryTestResp],
    responses=ERR_429,
)
async def test_draft_config(
    user: CurrentUser,
    r: RedisClient,
    request: Request,
    req: LLMConfigTestReq,
) -> ApiResponse[LLMConfigDryTestResp]:
    """保存前连通测试（不落库）。

    作用：用 provider + model + apikey + base_url 发最小 completion。
    场景：LLM 配置表单保存前验证；按用户限流防成本放大。
    参数：user/r — 用户与 Redis；req — 待测配置体。
    返回：ApiResponse，data 为 LLMConfigDryTestResp；限流 429。
    """
    await check_rate_limit(
        r,
        f"rl:llm-probe:{user.id}",
        settings.llm_probe_rate_limit_per_min,
        60,
    )
    return ApiResponse(data=await services.test_draft_config(req))


@router.patch("/{config_id}", response_model=ApiResponse[LLMConfigResp], responses=ERR_404)
async def patch_config(
    user: CurrentUser, db: DbSession, config_id: UUID, req: LLMConfigPatch
) -> ApiResponse[LLMConfigResp]:
    """部分更新 LLM 配置。

    作用：修改 provider/model/base_url/默认标记等字段。
    场景：设置页编辑已有 LLM 配置。
    参数：user/db — 用户与存储；config_id — 配置 ID；req — 待更新字段。
    返回：ApiResponse，data 为 LLMConfigResp；不存在 404。
    """
    return ApiResponse(data=await services.patch_config(db, user, config_id, req))


@router.delete(
    "/{config_id}",
    response_model=ApiResponse[LLMConfigDeleteResp],
    responses={**ERR_404, **ERR_409},
)
async def delete_config(
    user: CurrentUser, db: DbSession, config_id: UUID
) -> ApiResponse[LLMConfigDeleteResp]:
    """删除 LLM 配置。

    作用：删除指定配置；默认配置须先指定新默认。
    场景：设置页移除 LLM 配置。
    参数：user/db — 用户与存储；config_id — 配置 ID。
    返回：ApiResponse，data 为 LLMConfigDeleteResp；删默认且无替代 409。
    """
    return ApiResponse(data=await services.delete_config(db, user, config_id))


@router.post(
    "/{config_id}/test",
    response_model=ApiResponse[LLMConfigTestResp],
    responses={**ERR_404, **ERR_429},
)
async def test_config(
    user: CurrentUser,
    db: DbSession,
    r: RedisClient,
    request: Request,
    config_id: UUID,
) -> ApiResponse[LLMConfigTestResp]:
    """对已存 LLM 配置执行连通测试。

    作用：用库中 apikey 发最小 completion 验证连通性。
    场景：设置页「测试」按钮；按用户限流防成本放大。
    参数：user/db/r — 用户与存储；config_id — 配置 ID。
    返回：ApiResponse，data 为 LLMConfigTestResp；不存在 404，限流 429。
    """
    # 已存配置连通测试：真实付费 LLM 调用，按用户限流防成本放大
    await check_rate_limit(
        r,
        f"rl:llm-probe:{user.id}",
        settings.llm_probe_rate_limit_per_min,
        60,
    )
    return ApiResponse(data=await services.test_config(db, user, config_id))
