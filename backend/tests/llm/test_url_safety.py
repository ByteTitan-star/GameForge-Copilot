"""ADR-07 P1-19: openai_compat base_url SSRF checks."""

import pytest

from app.core.errors import AppError
from app.llm.url_safety import validate_llm_base_url


def test_https_public_host_ok() -> None:
    validate_llm_base_url("https://api.openai.com/v1", env="production")


def test_http_localhost_ok_in_development() -> None:
    validate_llm_base_url("http://127.0.0.1:11434", env="development")


def test_http_localhost_rejected_in_production() -> None:
    with pytest.raises(AppError):
        validate_llm_base_url("http://127.0.0.1:11434", env="production")


def test_rejects_link_local_metadata() -> None:
    with pytest.raises(AppError):
        validate_llm_base_url("http://169.254.169.254/latest", env="production")


def test_rejects_private_ip() -> None:
    with pytest.raises(AppError):
        validate_llm_base_url("https://10.0.0.1/v1", env="production")


def test_rejects_non_http_scheme() -> None:
    with pytest.raises(AppError):
        validate_llm_base_url("file:///etc/passwd", env="development")


def test_empty_ok() -> None:
    validate_llm_base_url(None, env="production")
    validate_llm_base_url("  ", env="production")
