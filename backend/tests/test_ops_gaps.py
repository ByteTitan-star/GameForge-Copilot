"""覆盖 1–16 缺口项：ready / models / 配额覆盖 / 并发 / 通知 / metrics / 日志。"""

import json
import logging
import uuid

import httpx
import pytest
from sqlalchemy import select

from app.core import db
from app.core.config import settings
from app.core.logging import JsonFormatter, setup_logging
from app.hosting import store
from app.llm import provider as llm_provider
from app.models.game import Game
from app.models.game_version import GameVersion
from app.usage import quota as quota_mod


async def test_ready_ok(client: httpx.AsyncClient) -> None:
    r = await client.get("/ready")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["db"] is True
    assert data["redis"] is True
    assert data["rabbitmq"] is True


async def test_metrics_endpoint(client: httpx.AsyncClient) -> None:
    await client.get("/healthz")
    r = await client.get("/metrics")
    assert r.status_code == 200
    assert "gameforge_http_requests_total" in r.text


def test_json_logging_format(capsys: pytest.CaptureFixture[str]) -> None:
    setup_logging("INFO", log_dir="-")
    logging.getLogger("test.json").info("hello-ops")
    out = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(out)
    assert payload["message"] == "hello-ops"
    assert payload["level"] == "INFO"
    assert "ts" in payload
    # Formatter 自身可序列化
    assert JsonFormatter().format(logging.LogRecord("x", 20, "", 0, "m", (), None))


async def test_list_models_fallback(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _whitelist(provider, apikey, base_url=None):
        return list(llm_provider._MODEL_WHITELIST[provider])

    monkeypatch.setattr(llm_provider, "list_models", _whitelist)
    r = await auth_client.get("/api/v1/me/llm-configs/models", params={"provider": "openai"})
    assert r.status_code == 200
    assert "gpt-4o" in r.json()["data"]


async def test_per_user_quota_override(
    admin_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
    me_user_id: uuid.UUID,
    redis_client,
) -> None:
    r = await admin_client.patch(
        f"/api/v1/admin/users/{me_user_id}",
        json={"daily_token_limit": 100},
    )
    assert r.status_code == 200, r.text
    assert await quota_mod.get_user_daily_limit(redis_client, me_user_id, 999) == 100
    usage = await auth_client.get("/api/v1/me/usage")
    assert usage.status_code == 200
    assert usage.json()["data"]["quota"]["daily_token_limit"] == 100


async def test_concurrent_run_limit(verified_client: httpx.AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_concurrent_runs", 1)
    g = await verified_client.post(
        "/api/v1/games", json={"title": "a", "requirement": "r"}
    )
    gid = g.json()["data"]["game_id"]
    r1 = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json={"requirement": "go"}
    )
    assert r1.status_code == 201, r1.text
    r2 = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json={"requirement": "go2"}
    )
    assert r2.status_code == 429
    assert r2.json()["error"]["code"] == "RATE_LIMITED"


async def test_draft_limit(verified_client: httpx.AsyncClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_drafts_per_user", 1)
    r1 = await verified_client.post(
        "/api/v1/games", json={"title": "a", "requirement": "r"}
    )
    assert r1.status_code == 201
    r2 = await verified_client.post(
        "/api/v1/games", json={"title": "b", "requirement": "r"}
    )
    assert r2.status_code == 429


async def test_approve_sends_notification(
    verified_client: httpx.AsyncClient,
    admin_client: httpx.AsyncClient,
    notifications: list,
) -> None:
    g = await verified_client.post(
        "/api/v1/games", json={"title": "NotifyMe", "requirement": "r"}
    )
    gid = uuid.UUID(g.json()["data"]["game_id"])
    await store.write_artifact(gid, 1, {"index.html": "<html></html>"})
    async with db.SessionLocal() as s:
        game = (await s.scalars(select(Game).where(Game.id == gid))).first()
        assert game is not None
        game.current_version = 1
        s.add(
            GameVersion(
                game_id=gid, version=1, artifact_path=f"{gid}/1/index.html", design_doc={}
            )
        )
        await s.commit()
    sub = await verified_client.post(
        f"/api/v1/games/{gid}/publish/submit", json={"version": 1}
    )
    pr_id = sub.json()["data"]["publish_request_id"]
    r = await admin_client.post(f"/api/v1/publish/{pr_id}/approve")
    assert r.status_code == 200, r.text
    assert any("上架" in s for _, s, _ in notifications)


async def test_smtp_send_uses_aiosmtplib(monkeypatch: pytest.MonkeyPatch) -> None:
    """#15：真实 SMTP 路径调用 aiosmtplib（无 host 时仍走控制台）。"""
    from app.email import worker

    sent: dict = {}

    async def _fake_send(msg, **kwargs):
        sent["to"] = msg["To"]
        sent["from"] = msg["From"]
        sent["kwargs"] = kwargs

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_from", "noreply@example.com")
    monkeypatch.setattr(settings, "smtp_from_name", "GameForge")
    monkeypatch.setattr(settings, "smtp_user", "u")
    monkeypatch.setattr(settings, "smtp_pass", "p")
    monkeypatch.setattr(worker.aiosmtplib, "send", _fake_send)
    await worker.send_notification_email({}, "a@b.com", "subj", "body")
    assert sent["to"] == "a@b.com"
    assert "GameForge" in sent["from"]
    assert "noreply@example.com" in sent["from"]
    assert sent["kwargs"]["hostname"] == "smtp.example.com"


async def test_docker_sandbox_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.sandbox import get_sandbox, reset_sandbox_for_tests
    from app.sandbox.docker import DockerSandbox

    monkeypatch.setattr(settings, "sandbox_backend", "docker")
    reset_sandbox_for_tests()
    assert isinstance(get_sandbox(), DockerSandbox)
    monkeypatch.setattr(settings, "sandbox_backend", "local")
    reset_sandbox_for_tests()


def test_transport_reset_noise_downgraded() -> None:
    """Windows _call_connection_lost 的 ConnectionResetError 应被识别为可降级噪音。"""
    from app.messaging.worker import _is_transport_reset_noise

    assert _is_transport_reset_noise(
        {
            "message": "Exception in callback "
            "_ProactorBasePipeTransport._call_connection_lost(None)",
            "exception": ConnectionResetError(),
        }
    )
    # 业务层的 ConnectionResetError（非 transport 回调）→ 不是噪音，照常上报
    assert not _is_transport_reset_noise(
        {"message": "SMTP send failed", "exception": ConnectionResetError()}
    )
    # 其他异常 → 不是噪音
    assert not _is_transport_reset_noise(
        {"message": "boom", "exception": RuntimeError()}
    )
