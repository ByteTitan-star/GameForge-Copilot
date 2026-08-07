"""测试基础设施：aiosqlite in-memory + fakeredis + memory 消息总线 + 依赖覆盖。

`uv run pytest` 无需 docker。每测建表/清表隔离；email enqueue 替换为捕获。
"""

import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core import db as db_module
from app.core.config import settings
from app.core.db import get_db
from app.core.redis import get_redis
from app.email import queue as email_queue
from app.forge import queue as forge_queue
from app.main import app
from app.messaging.factory import reset_messaging
from app.models import Base

# 单连接 in-memory sqlite（StaticPool 保证 create_all 与查询同一库）
_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, future=True
)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)

# email -> token（按用途前缀），供测试读取验证/重置 token；notify 列表存通知
_sent: dict[str, str] = defaultdict(str)
_notifications: list[tuple[str, str, str]] = []
_fake: fakeredis.aioredis.FakeRedis | None = None
_real_enqueue = forge_queue.enqueue_run
_real_enqueue_resume = forge_queue.enqueue_resume
_real_db_session = db_module.SessionLocal


async def _noop_enqueue(_run_id: uuid.UUID) -> None:
    """测试不跑 RabbitMQ worker；execute_run/resume_run 由测试直接调用。"""
    return None


async def _noop_enqueue_resume(_run_id: uuid.UUID, _decision: str, _modify: str | None) -> None:
    return None


@pytest.fixture(autouse=True)
def _playtest_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认试玩通过；个别测试单独 mock 失败。"""
    from app.sandbox.playtest import PlaytestResult

    async def _ok(_html: str) -> PlaytestResult:
        return PlaytestResult(ok=True, errors=[], console_logs=["mock playtest ok"])

    monkeypatch.setattr("app.forge.graph.run_playtest", _ok)


@pytest.fixture
def _fake_llm(monkeypatch: pytest.MonkeyPatch):
    """mock call_llm：plan 返 JSON，code 返 HTML。"""
    from app.llm.provider import Usage

    async def _fake(db, r, user_id, config_id, system, user_msg, **kwargs):
        if "JSON" in system or "策划" in system:
            return (
                '{"title":"测试游戏","gameplay":"stub design","controls":"方向键",'
                '"levels":["关卡1"]}',
                Usage(10, 5),
            )
        if "HTML5" in system:
            return (
                "<html><body><canvas id='c'></canvas>"
                "<button>play</button><script></script></body></html>",
                Usage(20, 10),
            )
        if "质检辅助" in system:
            return "试玩摘要 ok", Usage(5, 3)
        return "stub design doc", Usage(10, 5)

    from app.llm import client as llm_client

    monkeypatch.setattr(llm_client, "call_llm", _fake)
    return _fake


async def _get_test_db() -> AsyncIterator[AsyncSession]:
    async with _SessionLocal() as session:
        yield session


async def _get_test_redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    global _fake
    if _fake is None:
        _fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield _fake


async def _capture_verify(email: str, code: str) -> None:
    _sent[f"verify:{email}"] = code


async def _capture_reset(email: str, token: str) -> None:
    _sent[f"reset:{email}"] = token


async def _capture_notify(email: str, subject: str, body: str) -> None:
    _notifications.append((email, subject, body))


@pytest_asyncio.fixture(autouse=True)
async def _env(tmp_path: Path) -> AsyncIterator[dict[str, str]]:
    """每测：建表 + 覆盖依赖 + 捕获邮件 + 新建 fakeredis + hosting 指向 tmp；测后清。"""
    global _fake
    _fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    _orig_hosting = settings.hosting_root
    _orig_messaging = settings.messaging_backend
    _orig_admin_contact = settings.admin_contact_email
    settings.hosting_root = str(tmp_path)
    settings.messaging_backend = "memory"
    settings.admin_contact_email = ""
    reset_messaging()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = _get_test_db
    app.dependency_overrides[get_redis] = _get_test_redis
    email_queue.enqueue_verification = _capture_verify  # type: ignore[assignment]
    email_queue.enqueue_reset = _capture_reset  # type: ignore[assignment]
    email_queue.enqueue_notification = _capture_notify  # type: ignore[assignment]
    forge_queue.enqueue_run = _noop_enqueue  # type: ignore[assignment]
    forge_queue.enqueue_resume = _noop_enqueue_resume  # type: ignore[assignment]
    # forge.runner 用 db.SessionLocal 打开 session；swap 到测试 sessionmaker
    db_module.SessionLocal = _SessionLocal
    _sent.clear()
    _notifications.clear()
    yield _sent
    app.dependency_overrides.clear()
    db_module.SessionLocal = _real_db_session
    forge_queue.enqueue_run = _real_enqueue  # type: ignore[assignment]
    forge_queue.enqueue_resume = _real_enqueue_resume  # type: ignore[assignment]
    settings.hosting_root = _orig_hosting
    settings.messaging_backend = _orig_messaging
    settings.admin_contact_email = _orig_admin_contact
    reset_messaging()
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    if _fake is not None:
        await _fake.aclose()
        _fake = None


@pytest_asyncio.fixture
async def notifications(_env: dict[str, str]) -> list[tuple[str, str, str]]:
    return _notifications


@pytest_asyncio.fixture
async def redis_client(_env: dict[str, str]) -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    """与 endpoint 同一 fakeredis 实例，测试可直接 seed usage。"""
    assert _fake is not None
    yield _fake


@pytest_asyncio.fixture
async def sent(_env: dict[str, str]) -> dict[str, str]:
    """暴露捕获的邮件 token：sent[f'verify:{email}'] / sent[f'reset:{email}']。"""
    return _env


@pytest_asyncio.fixture
async def me_user_id(auth_client: httpx.AsyncClient) -> uuid.UUID:
    """auth_client 登录用户（u@b.com）的 id，供 usage 测试 seed。"""
    from sqlalchemy import select

    from app.models.user import User

    async with _SessionLocal() as s:
        user = (await s.scalars(select(User).where(User.email == "u@b.com"))).first()
        assert user is not None
        return user.id


@pytest_asyncio.fixture
async def db_session(_env: dict[str, str]) -> AsyncIterator[AsyncSession]:
    async with _SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _new_client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def auth_client() -> AsyncIterator[httpx.AsyncClient]:
    """注册+登录，带 Bearer 头；llm-config 等 me-scoped 端点用。独立 client 实例。"""
    async with _new_client() as client:
        await client.post(
            "/api/v1/auth/register", json={"email": "u@b.com", "password": "password123"}
        )
        resp = await client.post(
            "/api/v1/auth/login", json={"email": "u@b.com", "password": "password123"}
        )
        assert resp.status_code == 200, resp.text
        client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
        yield client


@pytest_asyncio.fixture
async def verified_client() -> AsyncIterator[httpx.AsyncClient]:
    """注册→验证邮箱→登录，带 Bearer 头；games/runs 端点需 email_verified。"""
    async with _new_client() as client:
        await client.post(
            "/api/v1/auth/register", json={"email": "v@b.com", "password": "password123"}
        )
        token = _sent["verify:v@b.com"]
        resp = await client.post(
            "/api/v1/auth/verify-email",
            json={"email": "v@b.com", "code": token},
        )
        assert resp.status_code == 200, resp.text
        resp = await client.post(
            "/api/v1/auth/login", json={"email": "v@b.com", "password": "password123"}
        )
        assert resp.status_code == 200, resp.text
        client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
        yield client


@pytest_asyncio.fixture
async def admin_client() -> AsyncIterator[httpx.AsyncClient]:
    """注册→DB 提权为 admin→登录，带 admin Bearer 头。独立 client 实例。"""
    from sqlalchemy import select

    from app.models.user import User

    async with _new_client() as client:
        await client.post(
            "/api/v1/auth/register",
            json={"email": "admin@b.com", "password": "password123"},
        )
        async with _SessionLocal() as s:
            user = (
                await s.scalars(select(User).where(User.email == "admin@b.com"))
            ).first()
            assert user is not None
            user.role = "admin"
            await s.commit()
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "admin@b.com", "password": "password123"},
        )
        assert resp.status_code == 200, resp.text
        client.headers["Authorization"] = f"Bearer {resp.json()['data']['access_token']}"
        yield client
