"""Structured JSON logging (docs/09). Stdlib only; stdout + optional file sink."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str = "backend") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def resolve_log_dir(log_dir: str) -> Path | None:
    """Resolve log directory; empty string → repo-root ``logs/``."""
    if log_dir == "-":
        return None
    if not log_dir:
        # backend/app/core/logging.py → repo root is parents[3]
        return Path(__file__).resolve().parents[3] / "logs"
    path = Path(log_dir)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def setup_logging(
    level: str = "INFO",
    *,
    service: str = "backend",
    log_dir: str = "",
) -> None:
    """Configure root logger: JSON to stdout and ``logs/{service}.log`` when enabled."""
    formatter = JsonFormatter(service=service)
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    root.addHandler(stdout)

    directory = resolve_log_dir(log_dir)
    if directory is not None:
        directory.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            directory / f"{service}.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
