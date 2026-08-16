"""生产级幂等/并发回归：

- create_run 的 Idempotency-Key 去重 + per-user 创建锁（吸收双击/重试，消除并发计数 TOCTOU）
- worker execute_run/resume_run 的执行锁（broker at-least-once 重投不重复执行）
- password/reset 与 LLM 连通测试的限流
- publish/submit 的部分唯一索引（并发 submit TOCTOU → 409）
"""

import uuid

import fakeredis.aioredis
import httpx
import pytest
from app.core import db
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import PublishStatus
from app.forge.runner import TaskLeaseBusy, execute_run
from app.hosting import store
from app.models.game import Game
from app.models.game_version import GameVersion
from app.models.publish_request import PublishRequest
from app.models.run_checkpoint import RunCheckpoint
from app.models.user import User
from sqlalchemy import select

GAME_BODY = {"title": "贪吃蛇", "requirement": "方向键"}
RUN_BODY = {"requirement": "加入加速道具"}
_HTML = "<html><body>game</body></html>"


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=GAME_BODY)
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_run(client: httpx.AsyncClient, gid: uuid.UUID) -> uuid.UUID:
    r = await client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["run_id"])


async def _make_version(gid: uuid.UUID, version: int = 1) -> None:
    await store.write_artifact(gid, version, {"index.html": _HTML})
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = version
        s.add(
            GameVersion(
                game_id=gid,
                version=version,
                artifact_path=f"{gid}/{version}/index.html",
                design_doc={},
            )
        )
        await s.commit()


async def _verified_user() -> User:
    async with db.SessionLocal() as s:
        user = (await s.scalars(select(User).where(User.email == "v@b.com"))).first()
        assert user is not None
        return user


# --------------------------------------------------------------------------- #
# create_run 幂等
# --------------------------------------------------------------------------- #


async def test_create_run_idempotency_key_dedup(
    verified_client: httpx.AsyncClient,
) -> None:
    """同一 Idempotency-Key 在 TTL 窗口内复用首次创建的 run，不重复建表/入队。"""
    gid = await _make_game(verified_client)
    headers = {"Idempotency-Key": "client-abc-123"}

    r1 = await verified_client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY, headers=headers)
    assert r1.status_code == 201, r1.text
    rid1 = r1.json()["data"]["run_id"]

    r2 = await verified_client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY, headers=headers)
    assert r2.status_code == 201, r2.text
    assert r2.json()["data"]["run_id"] == rid1  # 复用同一 run

    listed = await verified_client.get(f"/api/v1/games/{gid}/runs")
    matches = [r for r in listed.json()["data"] if r["run_id"] == rid1]
    assert len(matches) == 1  # 只创建了一条 run


async def test_create_run_distinct_idempotency_keys(
    verified_client: httpx.AsyncClient,
) -> None:
    """不同 Idempotency-Key 各自创建独立 run。"""
    gid = await _make_game(verified_client)
    r1 = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json=RUN_BODY, headers={"Idempotency-Key": "k1"}
    )
    r2 = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json=RUN_BODY, headers={"Idempotency-Key": "k2"}
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["data"]["run_id"] != r2.json()["data"]["run_id"]


async def test_create_run_lock_blocks_burst(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
) -> None:
    """预置创建锁（模拟并发中已有一个在创建）→ 第二个请求被 429 拦下，不入队。"""
    gid = await _make_game(verified_client)
    user = await _verified_user()
    await redis_client.set(f"run:create:{user.id}", "1", nx=True, ex=10)

    r = await verified_client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"

    listed = await verified_client.get(f"/api/v1/games/{gid}/runs")
    assert listed.json()["data"] == []  # 未创建任何 run


# --------------------------------------------------------------------------- #
# worker 执行锁（broker 重投去重）
# --------------------------------------------------------------------------- #


async def test_execute_run_requeues_when_already_executing(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """锁冲突必须抛错，让 broker 重投，不能正常返回并 ACK。"""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    await redis_client.set(f"run:executing:{rid}", "1", nx=True, ex=7200)

    with pytest.raises(TaskLeaseBusy):
        await execute_run({"redis": redis_client}, rid)

    r = await verified_client.get(f"/api/v1/runs/{rid}")
    d = r.json()["data"]
    assert d["status"] == "running"  # 未被推进到 HITL（paused）
    assert d["phase"] == "plan"


async def test_execute_run_releases_lock_on_completion(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """正常结束后执行锁释放，不阻塞后续 resume。"""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    await execute_run({"redis": redis_client}, rid)
    assert await redis_client.get(f"run:executing:{rid}") is None


async def test_redelivered_execute_does_not_restart_paused_run(
    verified_client: httpx.AsyncClient,
    redis_client: fakeredis.aioredis.FakeRedis,
    _fake_llm,
) -> None:
    """An execute redelivery after HITL pause is already handled and must be a no-op."""
    gid = await _make_game(verified_client)
    rid = await _make_run(verified_client, gid)
    await execute_run({"redis": redis_client}, rid)
    async with db.SessionLocal() as session:
        before = await session.get(RunCheckpoint, rid)
        assert before is not None
        revision = before.revision

    await execute_run({"redis": redis_client}, rid)

    async with db.SessionLocal() as session:
        after = await session.get(RunCheckpoint, rid)
        assert after is not None
        assert after.revision == revision


# --------------------------------------------------------------------------- #
# 限流
# --------------------------------------------------------------------------- #


async def test_password_reset_rate_limited(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """password/reset 超限 → 429（防邮件轰炸）。"""
    monkeypatch.setattr(settings, "default_rate_limit_per_min", 2)
    body = {"email": "victim@b.com"}
    for _ in range(2):
        r = await client.post("/api/v1/auth/password/reset", json=body)
        assert r.status_code == 200, r.text
    r = await client.post("/api/v1/auth/password/reset", json=body)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


async def test_llm_probe_rate_limited(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LLM 连通测试限流在 LLM 调用之前触发（limit=0 → 首次即 429，不发付费请求）。"""
    monkeypatch.setattr(settings, "llm_probe_rate_limit_per_min", 0)
    body = {
        "provider": "anthropic",
        "model": "claude-sonnet-5",
        "apikey": "sk-test",
        "base_url": None,
    }
    r = await auth_client.post("/api/v1/me/llm-configs/test", json=body)
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"


# --------------------------------------------------------------------------- #
# publish/submit 部分唯一索引（并发 TOCTOU → 409）
# --------------------------------------------------------------------------- #


async def test_publish_submit_concurrent_duplicate_returns_409(
    verified_client: httpx.AsyncClient,
) -> None:
    """game 仍 DRAFT 时，已存在 SUBMITTED 申请 → submit 命中部分唯一索引 → 409。"""
    from app.publish import services as publish_services

    gid = await _make_game(verified_client)
    await _make_version(gid, 1)
    user = await _verified_user()

    # 模拟并发中另一请求已抢先插入一条 SUBMITTED 申请（绕过 submit 的状态机前置）
    async with db.SessionLocal() as s:
        s.add(PublishRequest(game_id=gid, version=1, status=PublishStatus.SUBMITTED.value))
        await s.commit()

    # game 仍为 DRAFT（_SUBMITTABLE 通过），submit 尝试插入 → 唯一索引冲突 → 409
    async with db.SessionLocal() as s:
        with pytest.raises(AppError) as exc:
            await publish_services.submit(s, user, gid, 1, None)
        assert exc.value.code == ErrorCode.INVALID_STATE


async def test_publish_active_unique_allows_resubmit_after_reject(
    verified_client: httpx.AsyncClient,
    admin_client: httpx.AsyncClient,
) -> None:
    """部分唯一索引：rejected 行不占名额，驳回后可重新 submit（回归 test_reject_flow 关键点）。"""
    gid = await _make_game(verified_client)
    await _make_version(gid, 1)

    r = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    pr_id = r.json()["data"]["publish_request_id"]
    await admin_client.post(f"/api/v1/publish/{pr_id}/reject", json={"reason": "玩法问题"})

    # 驳回后重新 submit → 成功（rejected 行不在部分索引内，不冲突）
    r2 = await verified_client.post(f"/api/v1/games/{gid}/publish/submit", json={"version": 1})
    assert r2.status_code == 200, r2.text
