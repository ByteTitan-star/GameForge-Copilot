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
    """获取当前北京时间。

    作用：返回 Asia/Shanghai 时区的当前 datetime。
    场景：日志按北京日期分目录、时间戳格式化等。
    参数：无。
    返回：带时区信息的 datetime 对象。
    """
    return datetime.now(BEIJING)


def beijing_date_key(when: datetime | None = None) -> str:
    """生成按北京日期命名的日志目录键。

    作用：将 datetime 格式化为 ``YY-MM-DD`` 字符串，用于日志按日分文件夹。
    场景：DailyBeijingFileHandler 切换日志文件时确定当日目录名。
    参数：when - 指定时刻；为 None 时使用当前北京时间。
    返回：形如 ``26-08-07`` 的日期键字符串。
    """
    dt = when or beijing_now()
    return dt.strftime("%y-%m-%d")


def beijing_iso_from_timestamp(ts: float) -> str:
    """将 Unix 时间戳转为北京时区 ISO 字符串。

    作用：把秒级时间戳格式化为 Asia/Shanghai 的 ISO 8601 文本。
    场景：JsonFormatter 输出日志条目的 ts 字段。
    参数：ts - Unix 时间戳（秒）。
    返回：ISO 格式时间字符串。
    """
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
    """合并并绑定请求级结构化日志上下文。

    作用：将 trace_id、run_id、user_id 等字段写入 contextvar，后续日志自动携带。
    场景：请求入口或任务开始时绑定一次，无需每条日志传参。
    参数：fields - 任意键值对，与已有上下文合并。
    返回：无。
    """
    current = _log_context.get() or {}
    _log_context.set({**current, **fields})


def clear_log_context() -> None:
    """清空当前协程的日志上下文。

    作用：重置 contextvar 为空字典，避免字段泄漏到下一请求。
    场景：请求结束或 worker 处理完一条消息后调用。
    参数：无。
    返回：无。
    """
    _log_context.set({})


class JsonFormatter(logging.Formatter):
    def __init__(self, *, service: str = "backend") -> None:
        """初始化 JSON 日志格式化器。

        作用：记录服务名，供每条日志 payload 的 service 字段使用。
        场景：setup_logging 创建 stdout 与文件 handler 时共用同一 formatter。
        参数：service - 服务标识，默认 ``backend``。
        返回：无。
        """
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        """将 LogRecord 序列化为单行 JSON 字符串。

        作用：合并时间、级别、contextvar 上下文、extra 字段与异常信息。
        场景：所有经 root logger 输出的日志最终经此方法格式化。
        参数：record - stdlib 日志记录对象。
        返回：UTF-8 JSON 字符串（ensure_ascii=False）。
        """
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
    """解析日志根目录路径。

    作用：将配置字符串转为绝对 Path；``-`` 表示仅 stdout、不落盘。
    场景：setup_logging 决定是否在 ``logs/YY-MM-DD/`` 下写文件。
    参数：log_dir - 空串为仓库根 ``logs/``；``-`` 禁用文件；否则为自定义路径。
    返回：日志根目录 Path，或 None 表示不写文件。
    """
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
        """初始化按北京日期滚动的文件处理器。

        作用：绑定日志根目录与服务名，延迟打开当日 RotatingFileHandler。
        场景：setup_logging 在 resolve_log_dir 非 None 时挂载到 root logger。
        参数：base_dir - 日志根目录；service - 日志文件名前缀（如 backend.log）。
        返回：无。
        """
        super().__init__()
        self.base_dir = base_dir
        self.service = service
        self._current_date: str | None = None
        self._stream: RotatingFileHandler | None = None

    def _open_for_date(self, date_key: str) -> RotatingFileHandler:
        """为指定日期键创建或打开轮转文件 handler。

        作用：在 ``base_dir/date_key/{service}.log`` 下创建 10MB 轮转日志文件。
        场景：日期切换或首次 emit 时由 _ensure_stream 调用。
        参数：date_key - beijing_date_key 返回的 YY-MM-DD 字符串。
        返回：已设置 formatter 的 RotatingFileHandler。
        """
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
        """确保当前北京日期对应的文件流已打开。

        作用：若日期变更或尚未打开，则关闭旧流并打开新日期的日志文件。
        场景：每次 emit 前调用，实现北京零点自动切换目录。
        参数：无。
        返回：当前有效的 RotatingFileHandler。
        """
        date_key = beijing_date_key()
        if date_key != self._current_date or self._stream is None:
            if self._stream is not None:
                self._stream.close()
            self._stream = self._open_for_date(date_key)
            self._current_date = date_key
        return self._stream

    def emit(self, record: logging.LogRecord) -> None:
        """写入一条日志到当日轮转文件。

        作用：经 _ensure_stream 获取 handler 后委托 emit；异常走 handleError。
        场景：logging 框架在文件 handler 上输出记录时调用。
        参数：record - 待写入的 LogRecord。
        返回：无。
        """
        try:
            self._ensure_stream().emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """关闭底层轮转文件流并释放资源。

        作用：关闭 _stream 后置空，再调用父类 close。
        场景：进程退出或 logging shutdown 时。
        参数：无。
        返回：无。
        """
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
    """配置根 logger：JSON 输出到 stdout 与可选按日文件。

    作用：清空旧 handler，挂载 JsonFormatter 的 stdout 与 DailyBeijingFileHandler。
    场景：应用或 worker 进程启动时调用一次。
    参数：level - 日志级别；service - 服务名；log_dir - 见 resolve_log_dir。
    返回：无。
    """
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
