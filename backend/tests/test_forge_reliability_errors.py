"""P0：统一错误分类 — Recoverable ≠ Run FAILED。"""

from __future__ import annotations

import httpx
import pytest

from app.forge.reliability.errors import (
    DataCorruption,
    FatalError,
    InvalidModelOutput,
    InvariantViolation,
    Provider5xx,
    ProviderRateLimit,
    ProviderTimeout,
    RecoverableError,
    SandboxOOM,
    SandboxTimeout,
    SecurityViolation,
    UserActionRequired,
    WorkerInterrupted,
    classify_exception,
    is_fatal,
    is_recoverable,
)


@pytest.mark.parametrize(
    "exc_type",
    [
        ProviderTimeout,
        ProviderRateLimit,
        Provider5xx,
        InvalidModelOutput,
        SandboxTimeout,
        SandboxOOM,
        WorkerInterrupted,
    ],
)
def test_recoverable_errors_are_not_fatal(exc_type: type[RecoverableError]) -> None:
    err = exc_type("boom")
    assert isinstance(err, RecoverableError)
    assert is_recoverable(err)
    assert not is_fatal(err)


@pytest.mark.parametrize(
    "exc_type",
    [DataCorruption, InvariantViolation, SecurityViolation],
)
def test_fatal_errors_are_not_recoverable(exc_type: type[FatalError]) -> None:
    err = exc_type("boom")
    assert isinstance(err, FatalError)
    assert is_fatal(err)
    assert not is_recoverable(err)


def test_user_action_required_is_neither_recoverable_nor_fatal() -> None:
    err = UserActionRequired("need confirm")
    assert not is_recoverable(err)
    assert not is_fatal(err)


def test_classify_httpx_timeout() -> None:
    classified = classify_exception(httpx.ReadTimeout("timed out"))
    assert isinstance(classified, ProviderTimeout)
    assert is_recoverable(classified)


def test_classify_httpx_429() -> None:
    req = httpx.Request("POST", "https://example.com")
    resp = httpx.Response(429, request=req)
    classified = classify_exception(httpx.HTTPStatusError("limited", request=req, response=resp))
    assert isinstance(classified, ProviderRateLimit)


def test_classify_httpx_502() -> None:
    req = httpx.Request("POST", "https://example.com")
    resp = httpx.Response(502, request=req)
    classified = classify_exception(httpx.HTTPStatusError("bad gateway", request=req, response=resp))
    assert isinstance(classified, Provider5xx)


def test_classify_unknown_defaults_to_recoverable_worker_interrupted() -> None:
    classified = classify_exception(RuntimeError("unexpected"))
    assert isinstance(classified, WorkerInterrupted)
    assert is_recoverable(classified)


def test_fatal_passthrough() -> None:
    original = InvariantViolation("broken")
    assert classify_exception(original) is original
