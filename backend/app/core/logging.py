"""Structured JSON logging (docs/09). Stdlib only; stdout + optional file sink."""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

BEIJING = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    return datetime.now(BEIJING)


def beijing_date_key(when: datetime | None = None) -> str:
    """Daily log folder name, e.g. ``26-08-07`` (YY-MM-DD, Asia/Shanghai)."""
    dt = when or beijing_now()
    return dt.strftime("%y-%m-%d")


def beijing_iso_from_timestamp(ts: float) -> str:
    return datetime.fromtimestamp(ts, BEIJING).isoformat()


# 请求级结构化字段：一次请求（如一次 run_generation）绑定 trace_id/run_id/user_id，
# 之后该上下文内每条日志都自动带上这些顶层字段，无需逐条传参。
# 用 contextvars 而非全局 dict，保证多任务/协程间互不串扰。
_log_context: contextvars.ContextVar[dict[str, object] | None] = contextvars.ContextVar(
    "gf_log_context", default=None
)

# stdlib LogRecord 固有属性（formatter 输出时跳过，只把它们当作「内部」字段）
_RECORD_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


def bind_log_context(**fields: object) -> None:
    """合并当前请求的上下文字段（trace_id/run_id/user_id 等），写入每条日志顶层。"""
    current = _log_context.get() or {}
    _log_context.set({**current, **fields})


def clear_log_context() -> None:
    """请求结束时清空上下文，避免跨请求（worker 连续消费多条消息）字段串扰。"""
    _log_context.set({})


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str = "backend") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": beijing_iso_from_timestamp(record.created),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 请求级字段（contextvar）：绑定后每条日志都带
        for key, value in (_log_context.get() or {}).items():
            payload[key] = value
        # 单条 extra 字段：logger.info(..., extra={...}) 的任意非保留键
        for key, value in record.__dict__.items():
            if key not in _RECORD_RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def resolve_log_dir(log_dir: str) -> Path | None:
    """Resolve log root; empty string → repo-root ``logs/``."""
    if log_dir == "-":
        return None
    if not log_dir:
        return Path(__file__).resolve().parents[3] / "logs"
    path = Path(log_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


class DailyBeijingFileHandler(logging.Handler):
    """Append to ``logs/YY-MM-DD/{service}.log``; rolls folder at Beijing midnight."""

    def __init__(self, base_dir: Path, service: str) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.service = service
        self._current_date: str | None = None
        self._stream: RotatingFileHandler | None = None

    def _open_for_date(self, date_key: str) -> RotatingFileHandler:
        day_dir = self.base_dir / date_key
        day_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            day_dir / f"{self.service}.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        if self.formatter:
            handler.setFormatter(self.formatter)
        return handler

    def _ensure_stream(self) -> RotatingFileHandler:
        date_key = beijing_date_key()
        if date_key != self._current_date or self._stream is None:
            if self._stream is not None:
                self._stream.close()
            self._stream = self._open_for_date(date_key)
            self._current_date = date_key
        return self._stream

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._ensure_stream().emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        super().close()


def setup_logging(
    level: str = "INFO",
    *,
    service: str = "backend",
    log_dir: str = "",
) -> None:
    """Configure root logger: JSON to stdout and ``logs/YY-MM-DD/{service}.log``."""
    formatter = JsonFormatter(service=service)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    root.addHandler(stdout)

    directory = resolve_log_dir(log_dir)
    if directory is not None:
        file_handler = DailyBeijingFileHandler(directory, service)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
