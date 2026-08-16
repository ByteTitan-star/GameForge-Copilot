"""run_generation 异常日志分级：

AppError（业务错，如 LLM 未配置/apikey 错）→ WARNING 且不带 traceback，run FAILED；
其他瞬时/系统异常（RuntimeError 等）→ ERROR 且带 traceback，run PAUSED + recoverable_error。
"""

import logging
import uuid

import httpx
import pytest
from app.core.errors import AppError, ErrorCode
from app.forge import graph


async def _make_run(verified_client: httpx.AsyncClient) -> str:
    """通过 verified_client 创建 game + run，返回 run_id。"""
    gid = (
        await verified_client.post("/api/v1/games", json={"title": "t", "requirement": "r"})
    ).json()["data"]["game_id"]
    rid = (
        await verified_client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "r"})
    ).json()["data"]["run_id"]
    return rid


async def _noop_event(*_a, **_k) -> None:
    return None


async def test_app_error_logged_as_warning_without_traceback(
    verified_client: httpx.AsyncClient,
    redis_client,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """业务错（AppError）→ warning 一行，无 traceback，run FAILED。"""
    rid = await _make_run(verified_client)

    async def _boom(*_a, **_k):
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, "未配置默认 LLM")

    monkeypatch.setattr(graph, "_run_body", _boom)
    monkeypatch.setattr(graph, "publish_event", _noop_event)

    with caplog.at_level(logging.DEBUG):
        await graph.run_generation({"redis": redis_client}, uuid.UUID(rid))

    recs = [r for r in caplog.records if r.name == "app.forge.graph"]
    warns = [
        r
        for r in recs
        if r.levelno == logging.WARNING and "request failed (business)" in r.getMessage()
    ]
    errs = [r for r in recs if r.levelno == logging.ERROR]
    assert warns, "AppError 应产生 warning 日志"
    assert not errs, "AppError 不应产生 error 日志"
    assert warns[0].exc_info is None, "业务错日志不应带 traceback"

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    assert r.json()["data"]["status"] == "failed"


async def test_runtime_error_logged_as_exception_with_traceback(
    verified_client: httpx.AsyncClient,
    redis_client,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """系统错（RuntimeError）→ error + traceback；按 P0 进入可恢复暂停。"""
    rid = await _make_run(verified_client)

    async def _boom(*_a, **_k):
        raise RuntimeError("net boom")

    monkeypatch.setattr(graph, "_run_body", _boom)
    monkeypatch.setattr(graph, "publish_event", _noop_event)

    with caplog.at_level(logging.DEBUG):
        await graph.run_generation({"redis": redis_client}, uuid.UUID(rid))

    recs = [r for r in caplog.records if r.name == "app.forge.graph"]
    errs = [r for r in recs if r.levelno == logging.ERROR and "request failed" in r.getMessage()]
    assert errs, "RuntimeError 应产生 error 日志"
    assert errs[0].exc_info is not None, "系统错日志应带 traceback"

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    data = r.json()["data"]
    assert data["status"] == "paused"
    assert data["pause_reason"] == "recoverable_error"
    assert data["recovery"]["error_code"] == "worker_interrupted"
    assert data["recovery"]["can_retry"] is True
