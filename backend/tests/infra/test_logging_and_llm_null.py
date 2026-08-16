"""Logging file sink and LLM null-content guards."""

import json
import logging
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from app.core.logging import BEIJING, beijing_date_key, setup_logging
from app.enums import LLMProvider
from app.llm import provider
from app.llm.provider import Usage, _build_llm_client, complete

_FIXED = datetime(2026, 8, 7, 15, 51, 19, tzinfo=BEIJING)


def test_beijing_date_key() -> None:
    assert beijing_date_key(_FIXED) == "26-08-07"


def test_setup_logging_writes_dated_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.core.logging as logmod

    monkeypatch.setattr(logmod, "beijing_now", lambda: _FIXED)
    monkeypatch.setattr(logmod, "beijing_date_key", lambda when=None: "26-08-07")

    log_dir = str(tmp_path / "logs")
    setup_logging("INFO", service="backend", log_dir=log_dir)
    logging.getLogger("test.file").info("disk-log")
    for handler in logging.getLogger().handlers:
        handler.flush()
        handler.close()

    log_file = tmp_path / "logs" / "26-08-07" / "backend.log"
    content = log_file.read_text(encoding="utf-8")
    row = json.loads(content.strip().splitlines()[-1])
    assert row["service"] == "backend"
    assert row["message"] == "disk-log"
    assert "+08:00" in row["ts"]


@pytest.mark.asyncio
async def test_complete_coerces_null_openai_content(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "choices": [{"message": {"content": None}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 0},
            }

        text = ""

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, *_a: object, **_k: object) -> _Resp:
            return _Resp()

    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: _Client())
    content, usage = await complete(
        LLMProvider.OPENAI,
        "key",
        "gpt-4o",
        "sys",
        "user",
    )
    assert content == ""
    assert usage == Usage(input_tokens=1, output_tokens=0)


class _OkResp:
    status_code = 200
    text = ""

    @staticmethod
    def json() -> dict:
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }


class _CapturingClient:
    """记录 post 请求体，供断言 enable_thinking 是否注入。"""

    def __init__(self) -> None:
        self.last_json: object = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, _url: str, *, headers=None, json=None) -> _OkResp:
        self.last_json = json
        return _OkResp()


_DASHSCOPE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


@pytest.mark.asyncio
async def test_complete_injects_enable_thinking_for_qwen3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(
        LLMProvider.OPENAI_COMPAT, "key", "qwen3-max", "sys", "user", base_url=_DASHSCOPE
    )
    assert cap.last_json["enable_thinking"] is False


@pytest.mark.asyncio
async def test_complete_skips_enable_thinking_for_non_qwen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(LLMProvider.OPENAI, "key", "gpt-4o", "sys", "user")
    assert "enable_thinking" not in cap.last_json


@pytest.mark.asyncio
async def test_complete_respects_disable_thinking_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    monkeypatch.setattr(provider.settings, "llm_disable_thinking", False)
    await complete(
        LLMProvider.OPENAI_COMPAT, "key", "qwen3-max", "sys", "user", base_url=_DASHSCOPE
    )
    assert "enable_thinking" not in cap.last_json


@pytest.mark.asyncio
async def test_build_llm_client_bypasses_proxy_for_domestic_host() -> None:
    direct = _build_llm_client(f"{_DASHSCOPE}/chat/completions", httpx.Timeout(10))
    proxied = _build_llm_client("https://api.openai.com/v1/chat/completions", httpx.Timeout(10))
    try:
        # 国内 host 强制直连（trust_env=False）；海外 host 沿用系统代理（trust_env=True）
        assert direct.trust_env is False
        assert proxied.trust_env is True
    finally:
        await direct.aclose()
        await proxied.aclose()
