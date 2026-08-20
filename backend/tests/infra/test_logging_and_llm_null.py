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
    result = await complete(
        LLMProvider.OPENAI,
        "key",
        "gpt-4o",
        "sys",
        "user",
    )
    assert result.content == ""
    assert result.usage == Usage(input_tokens=1, output_tokens=0)


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
_BIGMODEL_ANTHROPIC = "https://open.bigmodel.cn/api/anthropic"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model",
    ["qwen3-max", "glm-5.1", "deepseek-v4-flash", "gpt-4o"],
)
async def test_complete_injects_enable_thinking_false_by_default(
    monkeypatch: pytest.MonkeyPatch,
    model: str,
) -> None:
    """OpenAI 兼容路径默认关 thinking（plan/审核都不需要思考链占满 max_tokens）。"""
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(LLMProvider.OPENAI_COMPAT, "key", model, "sys", "user", base_url=_DASHSCOPE)
    assert cap.last_json["enable_thinking"] is False


@pytest.mark.asyncio
async def test_complete_skips_enable_thinking_for_qwq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """纯推理模型注入 false 会 400，必须跳过。"""
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(LLMProvider.OPENAI_COMPAT, "key", "qwq-32b", "sys", "user", base_url=_DASHSCOPE)
    assert "enable_thinking" not in cap.last_json


@pytest.mark.asyncio
async def test_complete_disables_thinking_on_anthropic_native(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(LLMProvider.ANTHROPIC, "key", "claude-sonnet-5", "sys", "user")
    assert cap.last_json["thinking"] == {"type": "disabled"}
    assert "enable_thinking" not in cap.last_json


@pytest.mark.asyncio
async def test_complete_uses_anthropic_messages_for_anthropic_compat_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cap = _CapturingClient()
    monkeypatch.setattr("app.llm.provider.httpx.AsyncClient", lambda **_k: cap)
    await complete(
        LLMProvider.ANTHROPIC,
        "key",
        "glm-5.1",
        "sys",
        "user",
        base_url=_BIGMODEL_ANTHROPIC,
    )
    assert cap.last_json["system"] == "sys"
    assert cap.last_json["thinking"] == {"type": "disabled"}
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
