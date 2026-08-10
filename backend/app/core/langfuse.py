"""Langfuse 客户端生命周期与观测助手（docs/02 §可观测）。

为什么需要启动期显式注册：v4 SDK 的 get_client() 在无已注册实例时改读 os.environ，
而我们的 key 来自 .env（pydantic settings），两者不通——故必须在进程启动时构造一次
Langfuse(public_key=..., secret_key=..., base_url=...) 注册单例，后续 get_client()
才复用这些凭据。未配置 key 时全程空操作，单测/本地零依赖、零外发。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)
_registered = False


def init_langfuse() -> None:
    """启动期按 settings 注册 Langfuse 单例；幂等。"""
    global _registered
    if _registered:
        return
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        # 未配置 key：把 SDK 自身的鉴权 WARNING（"initialized without public_key"）
        # 提到 ERROR 之上，避免它在每次任务里反复刷屏污染日志
        logging.getLogger("langfuse").setLevel(logging.CRITICAL)
        log.info("langfuse disabled (no keys configured)")
        return
    from langfuse import Langfuse

    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )
    _registered = True
    log.info("langfuse registered base_url=%s", settings.langfuse_base_url)


def flush_langfuse() -> None:
    """停机前 flush 缓冲 trace；未注册/失败均不抛（停机路径不能阻塞）。"""
    if not _registered:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        log.exception("langfuse flush failed")


def _client() -> Any:
    """返回已注册的 langfuse client；未配置 key 时返回 None。

    调用前先确保单例已注册（init 幂等），避免 get_client() 落到读 os.environ 的兜底路径，
    也避免把 .env 里的 key 误判为未配置而静默禁用。
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    init_langfuse()
    from langfuse import get_client

    return get_client()


@contextmanager
def observe_span(name: str, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
    """包一层 span；未配置 key 时 yield None，调用方据此跳过后续 update。"""
    client = _client()
    if client is None:
        yield None
        return
    with client.start_as_current_observation(
        as_type="span", name=name, metadata=metadata
    ) as span:
        yield span


@contextmanager
def observe_generation(
    *,
    model: str,
    provider: str,
    system: str,
    user_msg: str,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """包一层 LLM generation；未配置 key 时 yield None，调用方据此跳过 output/usage update。"""
    client = _client()
    if client is None:
        yield None
        return
    meta = {"provider": provider, **(metadata or {})}
    with client.start_as_current_observation(
        as_type="generation",
        name=f"llm:{provider}",
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        metadata=meta,
    ) as gen:
        yield gen
