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
    """对明文密码做 argon2 哈希。

    作用：生成可安全存储的 password_hash。
    场景：注册、改密、重置密码写入数据库前。
    参数：password — 用户明文密码。
    返回：argon2 哈希字符串。
    """
    return _pwd.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码是否与哈希匹配。

    作用：argon2 verify；哈希损坏或不匹配返回 False 而非抛错。
    场景：登录、改密时校验旧密码。
    参数：password — 明文密码；password_hash — 库中存储的哈希。
    返回：匹配为 True，否则 False。
    """
    try:
        _pwd.verify(password_hash, password)
        return True
    except VerificationError:
        return False


def create_access_token(*, user_id: uuid.UUID, role: str) -> str:
    """签发短期 access JWT。

    作用：HS256 编码 JWT，claims 含 sub/role/type=access/iat/exp。
    场景：登录、刷新 token 后返回给客户端。
    参数：user_id — 用户 ID；role — 用户角色字符串。
    返回：JWT 字符串。
    """
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
    """解码并校验 access JWT。

    作用：验证签名与过期时间后返回 payload。
    场景：current_user 依赖、WS query token 鉴权。
    参数：token — JWT 字符串。
    返回：payload 字典；失败抛 jwt.PyJWTError，由调用方转 AppError。
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def generate_refresh_token() -> str:
    """生成 opaque refresh token 随机串。

    作用：产生高熵 URL-safe 随机串，真实态存 Redis。
    场景：issue_refresh 写入 refresh:{token} 键。
    参数：无。
    返回：32 字节 urlsafe 随机字符串。
    """
    return secrets.token_urlsafe(32)
