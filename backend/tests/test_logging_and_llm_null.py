"""Logging file sink and LLM null-content guards."""

import json
import logging
from pathlib import Path

import pytest

from app.core.logging import setup_logging
from app.llm.provider import Usage, complete
from app.enums import LLMProvider


def test_setup_logging_writes_file(tmp_path: Path) -> None:
    log_dir = str(tmp_path / "logs")
    setup_logging("INFO", service="backend", log_dir=log_dir)
    logging.getLogger("test.file").info("disk-log")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = (tmp_path / "logs" / "backend.log").read_text(encoding="utf-8")
    row = json.loads(content.strip().splitlines()[-1])
    assert row["service"] == "backend"
    assert row["message"] == "disk-log"


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
