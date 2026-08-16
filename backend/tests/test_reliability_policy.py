"""ADR-09: node timeout budgets and retry_on exclusions."""

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.forge.reliability.policy import (
    _default_retry_on,
    resolve_node_run_timeout,
)


def test_done_node_has_fixed_timeout() -> None:
    assert resolve_node_run_timeout("done") == 30.0


def test_code_or_repair_budget_grows_when_build_enabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "build_pipeline_enabled", False)
    base = resolve_node_run_timeout("code_or_repair")
    monkeypatch.setattr(settings, "build_pipeline_enabled", True)
    monkeypatch.setattr(settings, "build_max_retries", 3)
    monkeypatch.setattr(settings, "builder_timeout_s", 300)
    assert resolve_node_run_timeout("code_or_repair") == base + 900.0


def test_retry_on_excludes_app_error() -> None:
    assert _default_retry_on(AppError(ErrorCode.VALIDATION_ERROR, "x")) is False


def test_retry_on_allows_generic() -> None:
    assert _default_retry_on(RuntimeError("boom")) is True


def test_retry_on_excludes_content_attacked_by_name() -> None:
    class ContentAttacked(Exception):
        pass

    assert _default_retry_on(ContentAttacked()) is False
