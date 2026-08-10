"""结构化日志：JsonFormatter 需把请求级 contextvar 字段与单条 extra 字段提升为顶层 JSON。

覆盖 docs/09 的结构化约定：run_id/user_id/trace_id/stage/duration 等必须是可检索的顶层键，
而非塞进 message 文本。保留 message 键（与既有 backend/worker/frontend 日志一致）。
"""

from __future__ import annotations

import json
import logging

from app.core.logging import (
    JsonFormatter,
    bind_log_context,
    clear_log_context,
)

_formatter = JsonFormatter(service="worker")


def _format(message: str = "hello world", extra: dict | None = None) -> dict:
    record = logging.LogRecord(
        "test.logger", logging.INFO, __file__, 1, message, None, None
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return json.loads(_formatter.format(record))


def setup_function() -> None:
    clear_log_context()


def teardown_function() -> None:
    clear_log_context()


def test_formatter_emits_base_fields_and_message_key() -> None:
    d = _format()
    assert d["message"] == "hello world"
    assert d["level"] == "INFO"
    assert d["service"] == "worker"
    assert d["logger"] == "test.logger"
    assert "ts" in d


def test_formatter_surfaces_request_context_fields() -> None:
    bind_log_context(trace_id="abc123", run_id="r-1", user_id="u-9")
    d = _format()
    assert d["trace_id"] == "abc123"
    assert d["run_id"] == "r-1"
    assert d["user_id"] == "u-9"


def test_context_fields_appear_on_every_line_without_extra() -> None:
    """绑定后即便该条日志未传 extra，也应自动带上请求级字段。"""
    bind_log_context(trace_id="t1")
    d = _format("no extra here")
    assert d["trace_id"] == "t1"
    assert d["message"] == "no extra here"


def test_formatter_surfaces_per_call_extra_fields() -> None:
    d = _format(extra={"stage": "code", "duration": 1.23, "input_tokens": 7})
    assert d["stage"] == "code"
    assert d["duration"] == 1.23
    assert d["input_tokens"] == 7


def test_context_and_extra_merge_without_collision() -> None:
    bind_log_context(trace_id="t", run_id="r")
    d = _format(extra={"stage": "http", "status": 200})
    assert d["trace_id"] == "t"
    assert d["run_id"] == "r"
    assert d["stage"] == "http"
    assert d["status"] == 200


def test_clear_log_context_resets_fields() -> None:
    bind_log_context(trace_id="x", run_id="y")
    clear_log_context()
    d = _format()
    assert "trace_id" not in d
    assert "run_id" not in d


def test_formatter_does_not_leak_stdlib_record_attrs() -> None:
    d = _format()
    # stdlib 内部字段不得泄到顶层（避免污染、避免误把 process/thread 当业务字段）
    for reserved in ("args", "levelno", "pathname", "module", "threadName"):
        assert reserved not in d


def test_formatter_includes_exc_info_on_error() -> None:
    record = logging.LogRecord(
        "test.logger",
        logging.ERROR,
        __file__,
        1,
        "boom",
        None,
        None,
    )
    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
    d = json.loads(_formatter.format(record))
    assert d["level"] == "ERROR"
    assert "RuntimeError" in d["exc_info"]
