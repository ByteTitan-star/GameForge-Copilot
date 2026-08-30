"""进程级共享 httpx.AsyncClient（连接池；#147 P1）。

Pinecone / Embedding 等出站 HTTP 复用同一客户端，避免每次请求新建 TCP。
`trust_env=False`：绕过 Windows 系统代理，保证本地 TEI / 内网 host 可达。
"""

from __future__ import annotations

import threading

import httpx

_lock = threading.Lock()
_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """懒创建共享 AsyncClient（limits + keepalive）。"""
    global _client
    with _lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                trust_env=False,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20,
                ),
            )
        return _client


async def aclose_http_client() -> None:
    """应用停机或测试 teardown：关闭共享客户端。"""
    global _client
    with _lock:
        client = _client
        _client = None
    if client is not None and not client.is_closed:
        await client.aclose()


def reset_http_client_for_tests() -> None:
    """测试用：丢弃单例引用（不 await close；配合 aclose 使用）。"""
    global _client
    with _lock:
        _client = None
