"""Structured JSON logging (docs/09). Stdlib only; stdout + optional file sink."""

from __future__ import annotations

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
