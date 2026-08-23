import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UserPublic


class RegisterReq(BaseModel):
    """RegisterReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResp(BaseModel):
    """RegisterResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    user_id: uuid.UUID
    email: str
    email_verified: bool = False


class LoginReq(BaseModel):
    """LoginReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    email: EmailStr
    password: str


class LoginResp(BaseModel):
    """LoginResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    access_token: str
    refresh_token: str
    expires_in: int
    user: UserPublic


class RefreshReq(BaseModel):
    """RefreshReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    refresh_token: str


class TokenResp(BaseModel):
    """TokenResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    access_token: str
    refresh_token: str
    expires_in: int


class VerifyEmailReq(BaseModel):
    """VerifyEmailReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationReq(BaseModel):
    """ResendVerificationReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    email: EmailStr


class ResendVerificationResp(BaseModel):
    """ResendVerificationResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    sent: bool = True


class VerifyEmailResp(BaseModel):
    """VerifyEmailResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    user_id: uuid.UUID
    email_verified: bool = True


class PasswordResetReq(BaseModel):
    """PasswordResetReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    email: EmailStr


class PasswordResetResp(BaseModel):
    """PasswordResetResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    sent: bool = True


class PasswordResetConfirmReq(BaseModel):
    """PasswordResetConfirmReq API 请求体。

    场景：对应端点入参 Pydantic 校验。"""

    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResp(BaseModel):
    """PasswordResetConfirmResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    user_id: uuid.UUID
    email: str
    reset: bool = True


class PasswordChangeReq(BaseModel):
    """登录态改密：校验旧密码后设新密码。"""

    old_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChangeResp(BaseModel):
    """PasswordChangeResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    user_id: uuid.UUID
    changed: bool = True
