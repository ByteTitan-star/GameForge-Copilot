"""并发消费：_run_one 的 ack/nack 生命周期（at-least-once）+ _consume 的 prefetch 并发。

不连真实 RabbitMQ：用 fake message/channel 复刻 aio_pika 的 message.process() 语义
（正常退出 ack，抛异常 nack(requeue) 并 re-raise）。重点锁住改造后的两条不变量：
  1. ack 持有到任务结束 —— 失败必须 nack 重投，不能丢消息。
  2. 每条消息独立 task —— 多条消息的 dispatch 能真正并发，慢 LLM 不阻塞后续消费。
"""

from __future__ import annotations

import asyncio

import pytest

from app.core import langfuse as lf
from app.core.config import settings
from app.messaging import worker as worker_mod
from app.messaging.tasks import encode_task


class _FakeProcess:
    """复刻 aio_pika message.process() 的 ack/nack 语义。"""

    def __init__(self, message: _FakeMessage, requeue: bool) -> None:
        self._message = message
        self._requeue = requeue

    async def __aenter__(self) -> _FakeProcess:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            await self._message.ack()
        else:
            await self._message.nack(requeue=self._requeue)
        return False  # 不吞异常，re-raise


class _FakeMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.nack_requeue: bool | None = None

    def process(self, *, requeue: bool = False) -> _FakeProcess:
        return _FakeProcess(self, requeue)

    async def ack(self) -> None:
        self.acked = True

    async def nack(self, *, requeue: bool = False) -> None:
        self.nack_requeue = requeue


class _FakeQueueIterator:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages

    async def __aenter__(self) -> _FakeQueueIterator:
        self._it = iter(self._messages)
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def __aiter__(self) -> _FakeQueueIterator:
        return self

    async def __anext__(self) -> _FakeMessage:
        try:
            return next(self._it)
        except StopIteration as exc:
            raise StopAsyncIteration from exc


class _FakeQueue:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages

    def iterator(self) -> _FakeQueueIterator:
        return _FakeQueueIterator(self._messages)


class _FakeChannel:
    def __init__(self, messages: list[_FakeMessage]) -> None:
        self.prefetch: int | None = None
        self._messages = messages

    async def set_qos(self, *, prefetch_count: int) -> None:
        self.prefetch = prefetch_count

    async def declare_queue(self, name: str, **_: object) -> _FakeQueue:
        return _FakeQueue(self._messages)


async def _noop_async() -> None:
    return None


def _body() -> bytes:
    return encode_task("send_verification_email", {"email": "a@b.c", "code": "123"})


async def test_run_one_acks_on_success(monkeypatch) -> None:
    """任务成功 → 消息 ack，不 nack。"""
    msg = _FakeMessage(_body())
    seen: list[str] = []

    async def _dispatch(task: str, payload: dict) -> None:  # noqa: ARG001
        seen.append(task)

    monkeypatch.setattr(worker_mod, "dispatch_task", _dispatch)
    await worker_mod._run_one(msg)
    assert msg.acked is True
    assert msg.nack_requeue is None
    assert seen == ["send_verification_email"]


async def test_run_one_nacks_and_reraises_on_failure(monkeypatch) -> None:
    """任务抛异常 → nack(requeue=True) 重投，且异常继续上抛（at-least-once）。"""
    msg = _FakeMessage(_body())

    async def _boom(task: str, payload: dict) -> None:  # noqa: ARG001
        raise RuntimeError("boom")

    monkeypatch.setattr(worker_mod, "dispatch_task", _boom)
    with pytest.raises(RuntimeError, match="boom"):
        await worker_mod._run_one(msg)
    assert msg.acked is False
    assert msg.nack_requeue is True  # 重投


async def test_consume_sets_prefetch_and_dispatches_concurrently(monkeypatch) -> None:
    """_consume：prefetch 设为 max_concurrent_tasks；多条消息的 dispatch 真正并发（peak>1）。"""
    messages = [_FakeMessage(_body()) for _ in range(3)]
    channel = _FakeChannel(messages)

    async def _fake_task_channel() -> tuple[_FakeChannel, None]:
        return channel, None

    monkeypatch.setattr(worker_mod, "_task_channel", _fake_task_channel)
    monkeypatch.setattr(worker_mod, "close_connection", _noop_async)
    monkeypatch.setattr(lf, "flush_langfuse", lambda: None)

    release = asyncio.Event()
    in_flight = 0
    peak = 0

    async def _slow_dispatch(task: str, payload: dict) -> None:  # noqa: ARG001
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await release.wait()  # 阻塞，制造慢任务
        in_flight -= 1

    monkeypatch.setattr(worker_mod, "dispatch_task", _slow_dispatch)

    loop = asyncio.get_running_loop()
    old_handler = loop.get_exception_handler()
    try:
        consume_task = asyncio.create_task(worker_mod._consume())
        # 等所有 dispatch 并发起飞并在 release 处阻塞（_consume 卡在 gather）
        await asyncio.sleep(0.1)
        assert channel.prefetch == settings.max_concurrent_tasks
        assert peak == 3  # 三条并发，而非顺序（顺序消费 peak 只会是 1）
        assert all(m.acked is False for m in messages)  # 还没完成，未 ack

        release.set()  # 放行，任务陆续完成
        await asyncio.wait_for(consume_task, timeout=2)
    finally:
        loop.set_exception_handler(old_handler)

    assert all(m.acked is True for m in messages)
