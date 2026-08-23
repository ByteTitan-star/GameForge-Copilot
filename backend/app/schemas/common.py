import uuid

from pydantic import BaseModel

from app.enums import Role


class UserPublic(BaseModel):
    """用户公开信息 DTO。

    场景：登录响应、profile 等对外暴露字段。"""

    user_id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
