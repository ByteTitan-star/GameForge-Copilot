"""Logging file sink and LLM null-content guards."""

import json
import logging
from datetime import datetime
from pathlib import Path

import pytest

from app.core.logging import BEIJING, beijing_date_key, setup_logging
from app.enums import LLMProvider
from app.llm.provider import Usage, complete

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
