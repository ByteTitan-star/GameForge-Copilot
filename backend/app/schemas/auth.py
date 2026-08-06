import uuid

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import UserPublic


class RegisterReq(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResp(BaseModel):
    user_id: uuid.UUID
    email: str
    email_verified: bool = False


class LoginReq(BaseModel):
    email: EmailStr
    password: str


class LoginResp(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    user: UserPublic


class RefreshReq(BaseModel):
    refresh_token: str


class TokenResp(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int


class VerifyEmailReq(BaseModel):
    token: str


class VerifyEmailResp(BaseModel):
    user_id: uuid.UUID
    email_verified: bool = True


class PasswordResetReq(BaseModel):
    email: EmailStr


class PasswordResetResp(BaseModel):
    sent: bool = True


class PasswordResetConfirmReq(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetConfirmResp(BaseModel):
    user_id: uuid.UUID
    reset: bool = True
