"""用户反馈 → 管理员邮件端点（POST /api/v1/me/feedback）。

覆盖：正常提交、空 message、越权 run、超长 message、限流、邮件正文内容。
enqueue_notification 已被 conftest 全局替换为捕获，无需额外 mock。
"""

import uuid

import httpx
import pytest
from app.core.config import settings

GAME_BODY = {"title": "测试游戏", "requirement": "方向键移动"}
RUN_BODY = {"requirement": "加入加速道具"}


async def _make_game(client: httpx.AsyncClient) -> uuid.UUID:
    r = await client.post("/api/v1/games", json=GAME_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["game_id"])


async def _make_run(client: httpx.AsyncClient, gid: uuid.UUID) -> uuid.UUID:
    r = await client.post(f"/api/v1/games/{gid}/runs", json=RUN_BODY)
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["data"]["run_id"])


async def test_feedback_normal(
    verified_client: httpx.AsyncClient, notifications: list[tuple[str, str, str]]
) -> None:
    """带 message + error_summary 正常提交 → 200，通知邮件含 runId 与留言。"""
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    r = await verified_client.post(
        "/api/v1/me/feedback",
        json={
            "run_id": str(run_id),
            "message": "画面卡顿",
            "error_summary": "build timeout",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"submitted": True}

    assert len(notifications) == 1
    email, subject, body = notifications[0]
    assert str(run_id) in subject
    assert str(run_id) in body
    assert "画面卡顿" in body
    assert "build timeout" in body


async def test_feedback_empty_message_ok(
    verified_client: httpx.AsyncClient, notifications: list[tuple[str, str, str]]
) -> None:
    """message 为空 → 仍 200（可空提交），正文不含【用户反馈】段。"""
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    r = await verified_client.post(
        "/api/v1/me/feedback",
        json={"run_id": str(run_id), "message": ""},
    )
    assert r.status_code == 200, r.text
    assert len(notifications) == 1
    _, _, body = notifications[0]
    assert "【用户反馈】" not in body


async def test_feedback_non_owner_run_404(
    verified_client: httpx.AsyncClient,
    client: httpx.AsyncClient,
    sent: dict[str, str],
    notifications: list[tuple[str, str, str]],
) -> None:
    """另一用户的 run → GAME_NOT_FOUND，且不发邮件（防越权探测）。"""
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    # 第二个已验证用户
    await client.post("/api/v1/auth/register", json={"email": "x@b.com", "password": "password123"})
    code = sent["verify:x@b.com"]
    await client.post("/api/v1/auth/verify-email", json={"email": "x@b.com", "code": code})
    r = await client.post(
        "/api/v1/auth/login", json={"email": "x@b.com", "password": "password123"}
    )
    client.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"

    r = await client.post("/api/v1/me/feedback", json={"run_id": str(run_id)})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "GAME_NOT_FOUND"
    assert notifications == []


async def test_feedback_message_too_long_rejected(
    verified_client: httpx.AsyncClient,
    notifications: list[tuple[str, str, str]],
) -> None:
    """message 超 2000 字符 → 400 VALIDATION_ERROR（项目把 422 统一转 400），不发邮件。"""
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    r = await verified_client.post(
        "/api/v1/me/feedback",
        json={"run_id": str(run_id), "message": "x" * 2001},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert notifications == []


async def test_feedback_rate_limited(
    verified_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    notifications: list[tuple[str, str, str]],
) -> None:
    """打满限流后 → RATE_LIMITED，超额请求不发邮件。"""
    monkeypatch.setattr(settings, "default_rate_limit_per_min", 2)
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    body = {"run_id": str(run_id), "message": "a"}
    r1 = await verified_client.post("/api/v1/me/feedback", json=body)
    r2 = await verified_client.post("/api/v1/me/feedback", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200

    r3 = await verified_client.post("/api/v1/me/feedback", json=body)
    assert r3.status_code == 429
    assert r3.json()["error"]["code"] == "RATE_LIMITED"
    # 仅前两次成功发出
    assert len(notifications) == 2


async def test_feedback_requires_auth(client: httpx.AsyncClient) -> None:
    """未认证 → 401。"""
    r = await client.post("/api/v1/me/feedback", json={"run_id": str(uuid.uuid4())})
    assert r.status_code == 401


async def test_feedback_admin_email_resolved_from_env(
    verified_client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    notifications: list[tuple[str, str, str]],
) -> None:
    """ADMIN_CONTACT_EMAIL 环境变量优先：收件人为该配置值。"""
    monkeypatch.setattr(settings, "admin_contact_email", "ops@example.com")
    gid = await _make_game(verified_client)
    run_id = await _make_run(verified_client, gid)

    await verified_client.post("/api/v1/me/feedback", json={"run_id": str(run_id), "message": "hi"})
    assert len(notifications) == 1
    email, _, _ = notifications[0]
    assert email == "ops@example.com"
