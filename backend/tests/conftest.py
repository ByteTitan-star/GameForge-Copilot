"""测试基础设施：aiosqlite in-memory + fakeredis + memory 消息总线 + 依赖覆盖。

`uv run pytest` 无需 docker。每测建表/清表隔离；email enqueue 替换为捕获。
"""

import json
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
from app.hosting.factory import reset_hosting_for_tests
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

    async def _ok(_html: str, **_kwargs: object) -> PlaytestResult:
        return PlaytestResult(
            ok=True,
            errors=[],
            console_logs=["mock playtest ok"],
            motion_signal="raf",
        )

    for target in (
        "app.forge.graph.run_playtest",
        "app.forge.graph.run_playtest_dist",
        "app.forge.code_qa_exec.run_playtest",
        "app.forge.code_qa_exec.run_playtest_dist",
    ):
        monkeypatch.setattr(target, _ok)


def _valid_design_doc_json() -> str:
    """构造能通过 validate_design_doc 的 v2 设计稿，供 plan/revise 节点测试使用。"""
    return json.dumps(
        {
            "title": "测试游戏",
            "gameplay": "玩家操控方块在网格中收集金币并躲避障碍，达到目标分数通关。",
            "controls": ["方向键或 WASD 移动；触屏滑动改变方向"],
            "levels": ["第一关", "第二关"],
            "overview": {
                "genre": "休闲街机",
                "target_experience": "短局反应与路径规划",
                "session_length": "约 3 分钟",
                "scope": "单个离线 index.html 可运行的原型",
            },
            "core_loop": ["观察障碍与金币", "操作移动", "结算并进入下一关"],
            "rules": {
                "objectives": ["收集金币"],
                "win_conditions": ["达到目标分数"],
                "lose_conditions": ["撞到障碍"],
                "scoring": ["每枚金币 10 分"],
                "progression": ["难度递增"],
            },
            "game_states": [
                {"id": "menu", "purpose": "开始入口", "transitions": ["开始 -> playing"]},
                {
                    "id": "playing",
                    "purpose": "主玩法",
                    "transitions": [
                        "暂停 -> paused",
                        "通关 -> level_complete",
                        "失败 -> game_over",
                    ],
                },
                {"id": "paused", "purpose": "暂停", "transitions": ["继续 -> playing"]},
                {
                    "id": "level_complete",
                    "purpose": "过关结算",
                    "transitions": ["下一关 -> playing", "全部完成 -> victory"],
                },
                {"id": "game_over", "purpose": "失败结算", "transitions": ["重开 -> menu"]},
                {"id": "victory", "purpose": "通关", "transitions": ["重开 -> menu"]},
            ],
            "entities": [
                {
                    "id": "player",
                    "name": "玩家",
                    "type": "player",
                    "behavior": ["响应输入移动"],
                    "properties": {},
                }
            ],
            "level_specs": [
                {
                    "id": "level_1",
                    "name": "第一关",
                    "goal": "收集 5 金币",
                    "setup": ["生成玩家与障碍"],
                    "mechanics": ["移动收集"],
                    "difficulty": ["低速障碍"],
                    "completion": "达到 50 分",
                    "next": "level_2",
                },
                {
                    "id": "level_2",
                    "name": "第二关",
                    "goal": "收集 10 金币",
                    "setup": ["增加障碍密度"],
                    "mechanics": ["移动收集"],
                    "difficulty": ["高速障碍"],
                    "completion": "达到 100 分",
                    "next": "victory",
                },
            ],
            "ui": {
                "screens": ["主菜单", "游戏", "结算"],
                "hud": ["分数"],
                "feedback": ["得分提示"],
                "instructions": ["方向键移动"],
            },
            "presentation": {
                "visual_style": "扁平像素风",
                "color_palette": ["#111111", "#eeeeee"],
            },
            "engine": {
                "id": "canvas",
                "rationale": "网格收集玩法实体少、无物理碰撞，原生 Canvas 足够且零依赖。",
                "version": "",
                "library_notes": ["用 requestAnimationFrame 并钳制 delta time"],
            },
            "acceptance_criteria": [
                {
                    "id": f"AC-{i:02d}",
                    "requirement": req,
                    "verification": ver,
                }
                for i, (req, ver) in enumerate(
                    [
                        ("可从菜单开始游戏", "点击开始进入 playing"),
                        ("键盘可移动", "按方向键玩家移动"),
                        ("触控可移动", "触屏滑动改变方向"),
                        ("可暂停并继续", "暂停后继续正常运行"),
                        ("通关判定", "达分进入 level_complete"),
                        ("失败判定", "撞障碍进入 game_over"),
                        ("可重新开始", "结算后返回 menu 重开"),
                        ("无控制台错误", "试玩无 pageerror"),
                    ],
                    start=1,
                )
            ],
        },
        ensure_ascii=False,
    )


def _valid_art_options_json() -> str:
    return json.dumps(
        {
            "options": [
                {
                    "id": "A",
                    "name": "清透霓虹",
                    "summary": "Canvas 几何实体配合青色轨迹、命中粒子和高对比 HUD。",
                    "recommended": True,
                },
                {
                    "id": "B",
                    "name": "纸雕街机",
                    "summary": "CSS 层叠纸片、硬边阴影与逐帧形变构成轻量手作视觉。",
                    "recommended": False,
                },
            ]
        },
        ensure_ascii=False,
    )


def _valid_art_detail_json() -> str:
    return json.dumps(
        {
            "selected_option": "A",
            "name": "清透霓虹",
            "visual_concept": "用高对比几何轮廓和短促粒子强化移动、得分与碰撞反馈。",
            "implementation_principles": ["全部视觉由 Canvas 与 CSS 程序化绘制"],
            "palette": {"background": ["#07181c"], "accent": ["#25e6cf"]},
            "typography": {"display": "system-ui 700", "body": "system-ui 400"},
            "screens": [{"state": "playing", "layout": "HUD 顶置，游戏区居中"}],
            "hud": ["分数与关卡始终位于安全区"],
            "entities": [{"id": "player", "rendering": "Canvas 圆角几何体"}],
            "effects": ["得分时产生最多 16 个青色粒子"],
            "responsive": ["触屏时底部保留 72px 操作区"],
            "accessibility": ["状态变化同时使用形状和文本"],
            "performance": ["粒子对象池上限 48"],
            "avoid": ["不使用外部图片"],
            "acceptance_criteria": ["菜单、游玩和结算状态视觉可明确区分"],
        },
        ensure_ascii=False,
    )


@pytest.fixture
def _fake_llm(monkeypatch: pytest.MonkeyPatch):
    """mock call_llm + call_llm_stream：plan/revise 返合法 v2 设计稿 JSON，code/repair 返 HTML。

    新版 plan 节点会用 validate_design_doc 真实校验策划稿，最小四字段 JSON 会被
    拒绝并重试耗尽后抛错，因此这里必须返回结构完整的 v2 设计稿。QA 失败诊断在
    新版改走 HTML5 工程师视角的 QA_PROMPT，命中下方 HTML5 分支返回 HTML 字符串，
    诊断结果仅作为字符串透传给修复节点，不做解析。

    call_llm_stream 是流式门面，把 _fake 的完整内容切成 10 字一块 yield，末帧带 usage。
    """
    from app.enums import LLMProvider
    from app.llm.provider import StreamChunk, Usage

    def _decide(system: str):
        """按 system prompt 决定返回内容 + usage。流式/非流式共用。"""
        if "方向提案" in system or "上一轮两个视觉方向" in system:
            return _valid_art_options_json(), Usage(10, 5)
        if "前端动效负责人" in system:
            return _valid_art_detail_json(), Usage(20, 10)
        if "只生成一个自包含的 index.html" in system or "故障修复工程师" in system:
            return (
                "<html><body><canvas id='c'></canvas>"
                "<button>play</button><script></script></body></html>",
                Usage(20, 10),
            )
        if "JSON" in system or "策划" in system:
            return _valid_design_doc_json(), Usage(10, 5)
        return "stub design doc", Usage(10, 5)

    async def _fake(db, r, user_id, config_id, system, user_msg, **kwargs):
        content, usage = _decide(system)
        return content, usage, LLMProvider.ANTHROPIC

    async def _fake_stream(db, r, user_id, config_id, system, user_msg, **kwargs):
        content, usage = _decide(system)
        # 切成 10 字一块逐块 yield，末帧带 usage（对齐 provider.complete_stream 协议）
        for i in range(0, max(len(content), 1), 10):
            yield StreamChunk(delta=content[i : i + 10], usage=None)
        yield StreamChunk(delta="", usage=usage)

    from app.llm import client as llm_client

    monkeypatch.setattr(llm_client, "call_llm", _fake)
    monkeypatch.setattr(llm_client, "call_llm_stream", _fake_stream)
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
    _orig_hosting_backend = settings.hosting_backend
    _orig_messaging = settings.messaging_backend
    _orig_admin_contact = settings.admin_contact_email
    _orig_log_dir = settings.log_dir
    # langfuse：.env 可能带真实 key，测试全程禁用，避免 observe_* 触发云上报
    _orig_langfuse_pub = settings.langfuse_public_key
    _orig_langfuse_sec = settings.langfuse_secret_key
    settings.hosting_root = str(tmp_path)
    # hosting 强制 local：.env 切到 s3 时测试产物（含 60MB 配额用例）会泄进真实 OSS
    settings.hosting_backend = "local"
    settings.messaging_backend = "memory"
    settings.admin_contact_email = ""
    settings.log_dir = "-"
    settings.langfuse_public_key = ""
    settings.langfuse_secret_key = ""
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
    from app.forge.event_log import bind_event_redis

    bind_event_redis(_fake)
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
    settings.hosting_backend = _orig_hosting_backend
    reset_hosting_for_tests()
    settings.messaging_backend = _orig_messaging
    settings.admin_contact_email = _orig_admin_contact
    settings.log_dir = _orig_log_dir
    settings.langfuse_public_key = _orig_langfuse_pub
    settings.langfuse_secret_key = _orig_langfuse_sec
    reset_messaging()
    from app.forge.event_log import bind_event_redis

    bind_event_redis(None)
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
        # 预置默认 LLM 配置：create_run 前置校验要求用户有 is_default 配置
        from sqlalchemy import select

        from app.enums import LLMProvider
        from app.llm import crypto
        from app.models.llm_config import UserLLMConfig
        from app.models.user import User

        async with _SessionLocal() as s:
            user = (await s.scalars(select(User).where(User.email == "v@b.com"))).first()
            assert user is not None
            s.add(
                UserLLMConfig(
                    user_id=user.id,
                    provider=LLMProvider.ANTHROPIC.value,
                    model="claude-sonnet-5",
                    apikey_enc=crypto.encrypt_apikey("sk-test-verify"),
                    base_url=None,
                    is_default=True,
                )
            )
            await s.commit()
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


@pytest_asyncio.fixture
async def official_seeded(db_session: AsyncSession) -> None:
    from app.games.official import seed_official_games

    await seed_official_games(db_session)
