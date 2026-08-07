"""密码哈希与 token 原语：argon2 哈希、JWT access、opaque refresh 生成。"""

import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import settings

_pwd = PasswordHasher()


def hash_password(password: str) -> str:
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """哈希不匹配/损坏均返回 False（catch VerificationError 覆盖 VerifyMismatch/InvalidHash）。"""
    try:
        _pwd.verify(password_hash, password)
        return True
    except VerificationError:
        return False


def create_access_token(*, user_id: uuid.UUID, role: str) -> str:
    """签发短期 access JWT，HS256，claims 含 user_id/role/type=access。"""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=settings.jwt_access_ttl),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    """校验并解码；失败抛 jwt.PyJWTError，由调用方转 AppError。"""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def generate_refresh_token() -> str:
    """opaque refresh token：仅随机串，真实态落 Redis（见 tokens.py）。"""
    return secrets.token_urlsafe(32)
