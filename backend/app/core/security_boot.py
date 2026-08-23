"""Startup secret checks (ADR-07 / P0-1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

DEFAULT_JWT_SECRET = "dev-secret-change-me-to-a-32-byte-random-string"  # nosec B105


def assert_production_secrets(settings: Settings) -> None:
    """校验生产环境 JWT 密钥是否安全。

    作用：非 development 环境下拒绝使用默认或过短的 jwt_secret 启动。
    场景：应用启动时调用，防止生产环境误用开发默认密钥。
    参数：settings - 全局配置实例。
    返回：无；校验失败时抛出 RuntimeError。
    """
    if settings.env == "development":
        return
    secret = (settings.jwt_secret or "").strip()
    if secret == DEFAULT_JWT_SECRET or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a non-default value of at least 32 characters "
            f"when env={settings.env!r}"
        )
