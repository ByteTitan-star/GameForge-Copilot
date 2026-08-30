"""Knowledge RAG 进程内熔断（fail-open；#147 P0）。

与 LLM 熔断同构，但打开时不抛错：检索直接返回空结果并记 circuit_open，
避免 Pinecone / embedding 连续故障拖垮主 Agent 链路。
"""

from __future__ import annotations

import threading
import time

from app.core.config import settings

_lock = threading.Lock()
_failures = 0
_open_until = 0.0


def reset_knowledge_circuit() -> None:
    """测试 / 运维：清空熔断状态。"""
    global _failures, _open_until
    with _lock:
        _failures = 0
        _open_until = 0.0


def failure_count() -> int:
    with _lock:
        return _failures


def knowledge_circuit_is_open() -> bool:
    if not settings.knowledge_circuit_enabled:
        return False
    with _lock:
        if _open_until <= 0:
            return False
        return time.monotonic() < _open_until


def record_knowledge_failure() -> None:
    if not settings.knowledge_circuit_enabled:
        return
    global _failures, _open_until
    threshold = max(1, int(settings.knowledge_circuit_failure_threshold))
    open_s = max(0.0, float(settings.knowledge_circuit_open_s))
    with _lock:
        _failures += 1
        if _failures >= threshold:
            _open_until = time.monotonic() + open_s


def record_knowledge_success() -> None:
    if not settings.knowledge_circuit_enabled:
        return
    global _failures, _open_until
    with _lock:
        _failures = 0
        _open_until = 0.0
