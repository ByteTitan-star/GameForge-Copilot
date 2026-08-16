"""Startup secret checks (ADR-07 / P0-1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

DEFAULT_JWT_SECRET = "dev-secret-change-me-to-a-32-byte-random-string"


def assert_production_secrets(settings: Settings) -> None:
    """Refuse to boot outside development with a default or short JWT secret."""
    if settings.env == "development":
        return
    secret = (settings.jwt_secret or "").strip()
    if secret == DEFAULT_JWT_SECRET or len(secret) < 32:
        raise RuntimeError(
            "JWT_SECRET must be set to a non-default value of at least 32 characters "
            f"when env={settings.env!r}"
        )
