"""认证端点（M1 真实逻辑）：register/verify/login/refresh/logout + 密码重置。

路由薄，业务在 app.auth.services；错误经 AppError 转 ErrorResponse；限流走 Redis。
"""

from fastapi import APIRouter, Request, status

from app.auth import services
from app.auth.deps import CurrentUser, DbSession, RedisClient
from app.auth.ratelimit import check_rate_limit
from app.core.config import settings
from app.core.response import ApiResponse, ErrorResponse
from app.email import queue as email_queue
from app.enums import Role
from app.schemas.auth import (
    LoginReq,
    LoginResp,
    PasswordChangeReq,
    PasswordChangeResp,
    PasswordResetConfirmReq,
    PasswordResetConfirmResp,
    PasswordResetReq,
    PasswordResetResp,
    RefreshReq,
    RegisterReq,
    RegisterResp,
    ResendVerificationReq,
    ResendVerificationResp,
    TokenResp,
    VerifyEmailReq,
    VerifyEmailResp,
)
from app.schemas.common import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])

# docs/10 §3 错误码对应响应，供 openapi 标注
ERR_401 = {401: {"model": ErrorResponse, "description": "未认证或 token 失效"}}
ERR_400 = {400: {"model": ErrorResponse, "description": "token 无效或已过期"}}
ERR_409 = {409: {"model": ErrorResponse, "description": "邮箱已注册"}}
ERR_429 = {429: {"model": ErrorResponse, "description": "限流"}}


@router.post(
    "/register",
    response_model=ApiResponse[RegisterResp],
    status_code=201,
    responses={**ERR_409, **ERR_429},
)
async def register(
    req: RegisterReq, request: Request, db: DbSession, r: RedisClient
) -> ApiResponse[RegisterResp]:
    await check_rate_limit(
        r, f"rl:register:{request.client.host if request.client else 'na'}",
        settings.default_rate_limit_per_min, 60,
    )
    user, code = await services.register_user(db, req.email, req.password)
    await email_queue.enqueue_verification(user.email, code)
    return ApiResponse(data=RegisterResp(user_id=user.id, email=user.email))


@router.post("/login", response_model=ApiResponse[LoginResp], responses={**ERR_401, **ERR_429})
async def login(
    req: LoginReq, request: Request, db: DbSession, r: RedisClient
) -> ApiResponse[LoginResp]:
    await check_rate_limit(
        r, f"rl:login:{request.client.host if request.client else 'na'}",
        settings.default_rate_limit_per_min, 60,
    )
    user, access, refresh = await services.login_user(db, r, req.email, req.password)
    return ApiResponse(
        data=LoginResp(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_ttl,
            user=UserPublic(
                user_id=user.id, email=user.email,
                role=Role(user.role), email_verified=user.email_verified,
            ),
        )
    )


@router.post("/refresh", response_model=ApiResponse[TokenResp], responses=ERR_401)
async def refresh(req: RefreshReq, db: DbSession, r: RedisClient) -> ApiResponse[TokenResp]:
    access, new_refresh = await services.refresh_tokens(db, r, req.refresh_token)
    return ApiResponse(
        data=TokenResp(
            access_token=access, refresh_token=new_refresh, expires_in=settings.jwt_access_ttl
        )
    )


@router.post("/verify-email", response_model=ApiResponse[VerifyEmailResp], responses=ERR_400)
async def verify_email(req: VerifyEmailReq, db: DbSession) -> ApiResponse[VerifyEmailResp]:
    user = await services.verify_email(db, req.email, req.code)
    return ApiResponse(data=VerifyEmailResp(user_id=user.id))


@router.post(
    "/resend-verification",
    response_model=ApiResponse[ResendVerificationResp],
    responses=ERR_429,
)
async def resend_verification(
    req: ResendVerificationReq, request: Request, db: DbSession, r: RedisClient
) -> ApiResponse[ResendVerificationResp]:
    """重发 6 位邮箱验证码；防枚举恒返回 sent=true。"""
    await check_rate_limit(
        r,
        f"rl:resend-verify:{request.client.host if request.client else 'na'}:{req.email}",
        settings.default_rate_limit_per_min,
        60,
    )
    code = await services.resend_verification(db, req.email)
    if code is not None:
        await email_queue.enqueue_verification(req.email, code)
    return ApiResponse(data=ResendVerificationResp())


@router.post(
    "/password/reset",
    response_model=ApiResponse[PasswordResetResp],
    responses=ERR_429,
)
async def password_reset(
    req: PasswordResetReq, request: Request, db: DbSession, r: RedisClient
) -> ApiResponse[PasswordResetResp]:
    """防枚举：无论邮箱是否存在恒返回 sent=true。

    限流（IP+email）：避免对单一邮箱的邮件轰炸；与 resend-verification 一致。
    """
    await check_rate_limit(
        r,
        f"rl:reset:{request.client.host if request.client else 'na'}:{req.email}",
        settings.default_rate_limit_per_min,
        60,
    )
    result = await services.request_password_reset(db, req.email)
    if result is not None:
        email, token = result
        await email_queue.enqueue_reset(email, token)
    return ApiResponse(data=PasswordResetResp())


@router.post(
    "/password/reset/confirm",
    response_model=ApiResponse[PasswordResetConfirmResp],
    responses=ERR_400,
)
async def password_reset_confirm(
    req: PasswordResetConfirmReq, db: DbSession
) -> ApiResponse[PasswordResetConfirmResp]:
    user = await services.confirm_password_reset(db, req.token, req.new_password)
    return ApiResponse(
        data=PasswordResetConfirmResp(user_id=user.id, email=user.email)
    )


@router.post(
    "/password/change",
    response_model=ApiResponse[PasswordChangeResp],
    responses={**ERR_401, **ERR_400, 403: {"model": ErrorResponse, "description": "试用账号只读"}},
)
async def password_change(
    req: PasswordChangeReq, user: CurrentUser, db: DbSession
) -> ApiResponse[PasswordChangeResp]:
    """登录态改密（需 Bearer）；旧密码错误 → 401。"""
    updated = await services.change_password(user, db, req.old_password, req.new_password)
    return ApiResponse(data=PasswordChangeResp(user_id=updated.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(req: RefreshReq, r: RedisClient) -> None:
    """登出：refresh 从 Redis 删除，access 自然过期。"""
    await services.logout(r, req.refresh_token)
    return None


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, r: RedisClient) -> ApiResponse[dict]:
    from app.auth import oauth as oauth_mod

    return ApiResponse(data=await oauth_mod.oauth_start(r, provider))


@router.get("/oauth/{provider}/callback", response_model=ApiResponse[LoginResp])
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    db: DbSession,
    r: RedisClient,
) -> ApiResponse[LoginResp]:
    from app.auth import oauth as oauth_mod

    user, access, refresh = await oauth_mod.oauth_callback(db, r, provider, code, state)
    return ApiResponse(
        data=LoginResp(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.jwt_access_ttl,
            user=UserPublic(
                user_id=user.id,
                email=user.email,
                role=Role(user.role),
                email_verified=user.email_verified,
            ),
        )
    )
