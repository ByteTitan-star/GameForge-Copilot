import uuid

from pydantic import BaseModel

from app.enums import Role


class UserPublic(BaseModel):
    user_id: uuid.UUID
    email: str
    role: Role
    email_verified: bool
