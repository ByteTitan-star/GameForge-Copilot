"""ADR-07 P1-20: /dev routes require DEV_ROUTES_ENABLED."""

from app.core.config import Settings


def test_dev_routes_default_off() -> None:
    s = Settings(_env_file=None, dev_routes_enabled=False)
    assert s.dev_routes_enabled is False


def test_dev_routes_can_enable() -> None:
    s = Settings(_env_file=None, dev_routes_enabled=True)
    assert s.dev_routes_enabled is True
