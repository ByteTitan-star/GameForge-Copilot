"""ADR-07: production JWT secret fail-fast."""

import pytest

from app.core.config import Settings
from app.core.security_boot import DEFAULT_JWT_SECRET, assert_production_secrets


def test_assert_rejects_default_jwt_in_production() -> None:
    s = Settings(env="production", jwt_secret=DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_assert_rejects_short_jwt_in_production() -> None:
    s = Settings(env="staging", jwt_secret="x" * 16)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        assert_production_secrets(s)


def test_assert_allows_default_in_development() -> None:
    s = Settings(env="development", jwt_secret=DEFAULT_JWT_SECRET)
    assert_production_secrets(s)


def test_assert_allows_strong_secret_in_production() -> None:
    s = Settings(env="production", jwt_secret="a" * 32)
    assert_production_secrets(s)
