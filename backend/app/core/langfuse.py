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
    """启动期按 settings 注册 Langfuse 单例。

    作用：用 pydantic 配置构造 Langfuse 客户端并注册全局单例；未配置 key 时禁用并压低 SDK 日志级别。
    场景：应用或 worker 进程启动时调用；幂等，重复调用无副作用。
    参数：无。
    返回：无。
    """
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
    """停机前将缓冲的 trace 刷送到 Langfuse。

    作用：调用已注册客户端的 flush；未注册或失败均不抛异常。
    场景：进程优雅退出、worker 任务结束等停机路径。
    参数：无。
    返回：无。
    """
    if not _registered:
        return
    try:
        from langfuse import get_client

        get_client().flush()
    except Exception:
        log.exception("langfuse flush failed")


def _client() -> Any:
    """获取已注册的 Langfuse 客户端实例。

    作用：在 key 已配置时先 init_langfuse 再 get_client；避免 SDK 回退读 os.environ。
    场景：observe_span、propagate_trace_attrs 等内部助手调用。
    参数：无。
    返回：Langfuse 客户端；未配置 key 时返回 None。
    """
    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        return None
    init_langfuse()
    from langfuse import get_client

    return get_client()


@contextmanager
def observe_span(name: str, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
    """在上下文管理器中创建 Langfuse span 观测。

    作用：包装 client.start_as_current_observation(as_type=span)；无 key 时 yield None。
    场景：非 LLM 的业务步骤（如沙箱执行、缓存命中）需要 trace 分段时。
    参数：name - span 名称；metadata - 可选附加元数据。
    返回：上下文管理器，yield span 对象或 None。
    """
    client = _client()
    if client is None:
        yield None
        return
    with client.start_as_current_observation(as_type="span", name=name, metadata=metadata) as span:
        yield span


@contextmanager
def propagate_trace_attrs(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[None]:
    """在作用域内传播 Langfuse trace 属性。

    作用：通过 propagate_attributes 绑定 user_id、session_id、tags、metadata；无 key 时空操作。
    场景：一次 run 或请求入口包裹后续所有 observation。
    参数：user_id - 用户标识；session_id - 会话/run 标识；tags - 标签列表；metadata - 元数据。
    返回：上下文管理器，无 yield 值。
    """
    if _client() is None:
        yield
        return
    from langfuse import propagate_attributes

    kwargs: dict[str, Any] = {}
    if user_id is not None:
        kwargs["user_id"] = user_id
    if session_id is not None:
        kwargs["session_id"] = session_id
    if tags is not None:
        kwargs["tags"] = tags
    if metadata is not None:
        kwargs["metadata"] = metadata
    if not kwargs:
        yield
        return
    with propagate_attributes(**kwargs):
        yield


@contextmanager
def observe_generation(
    *,
    model: str,
    provider: str,
    system: str,
    user_msg: str,
    kind: str = "chat",
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any]:
    """在上下文管理器中创建 Langfuse LLM generation 观测。

    作用：记录 model、provider、system/user 输入；name 固定为 ``llm:{kind}``；无 key 时 yield None。
    场景：每次 LLM complete 调用前后包裹，便于 UI 区分 plan/guardrail 等场景。
    参数：model - 模型名；provider - 提供方；system/user_msg - 提示词；
    kind - 业务类型；metadata/tags - 附加信息。
    返回：上下文管理器，yield generation 对象或 None。
    """
    client = _client()
    if client is None:
        yield None
        return
    meta: dict[str, Any] = {"provider": provider, "kind": kind, **(metadata or {})}
    if tags:
        meta["_tags"] = list(tags)
    with client.start_as_current_observation(
        as_type="generation",
        name=f"llm:{kind}",
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        metadata=meta,
    ) as gen:
        yield gen
