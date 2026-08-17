"""LLM apikey 加密：Fernet。key 缺失时从 JWT_SECRET 经 PBKDF2 派生（确定性、跨重启稳定）。

明文 key 仅内存单次调用生命周期，不落日志（docs/05）。
"""

import base64

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import settings

_fernet: Fernet | None = None
_SALT = b"gameforge-llm-apikey-v1"


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key: str | bytes = settings.llm_apikey_encryption_key
        if not key:
            # dev fallback：从 jwt_secret 派生，保证跨重启可解密（prod 应显式配置）
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=_SALT, iterations=100_000)
            key = base64.urlsafe_b64encode(kdf.derive(settings.jwt_secret.encode()))
        _fernet = Fernet(key)
    return _fernet


def encrypt_apikey(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()


def try_decrypt_apikey(ciphertext: str) -> str | None:
    """解密失败返回 None（如加密密钥轮换后旧密文不可读），不抛异常。"""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        return None


def decrypt_apikey(ciphertext: str) -> str:
    """解密失败抛 AppError 由调用方处理；正常路径明文不落日志。"""
    from app.core.errors import AppError, ErrorCode

    plain = try_decrypt_apikey(ciphertext)
    if plain is None:
        raise AppError(
            ErrorCode.LLM_CONFIG_INVALID,
            "apikey 解密失败：可能 LLM_APIKEY_ENCRYPTION_KEY 或 JWT_SECRET 已变更，"
            "请删除该配置后重新添加",
        )
    return plain
