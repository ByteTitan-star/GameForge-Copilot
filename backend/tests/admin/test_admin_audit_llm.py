"""审核模型（护栏）admin 后台配置测试：加密写入、masked 回显、DB 优先 env、测试端点。"""

import httpx

from app.admin import services as admin_services
from app.forge import guard

_BASE_BODY = {
    "default_daily_token_limit": 500_000,
    "default_monthly_token_limit": 10_000_000,
    "default_rate_limit_per_min": 30,
    "admin_contact_email": "",
}


async def _put_audit(admin_client: httpx.AsyncClient, audit: dict) -> dict:
    r = await admin_client.put("/api/v1/admin/settings", json={**_BASE_BODY, "audit_llm": audit})
    assert r.status_code == 200, r.text
    return r.json()["data"]["audit_llm"]


async def test_audit_llm_write_encrypt_and_masked_echo(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    """PUT 明文 key → 落库密文（DB 里无明文）→ GET 回显 masked。"""
    await _put_audit(
        admin_client,
        {
            "enabled": True,
            "provider": "openai_compat",
            "model": "qwen-plus",
            "apikey": "sk-audit-test-123456",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        },
    )
    # 生效配置：明文 key 可解密回来
    cfg = await admin_services.get_audit_llm_config(db_session)
    assert cfg["model"] == "qwen-plus"
    assert cfg["apikey"] == "sk-audit-test-123456"

    # GET 回显 masked（不含明文）
    r = await admin_client.get("/api/v1/admin/settings")
    audit = r.json()["data"]["audit_llm"]
    assert audit["apikey"].startswith("sk-") and "***" in audit["apikey"]
    assert "sk-audit-test-123456" not in audit["apikey"]


async def test_audit_llm_keep_old_key_when_masked(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    """只改 model、apikey 传 masked → 保留旧密钥。"""
    await _put_audit(
        admin_client,
        {"enabled": True, "provider": "openai", "model": "gpt-4o", "apikey": "sk-old-key-9999"},
    )
    # 第二次提交：apikey 传 GET 回显的 masked 值
    r = await admin_client.get("/api/v1/admin/settings")
    masked = r.json()["data"]["audit_llm"]["apikey"]
    await _put_audit(
        admin_client,
        {"enabled": True, "provider": "openai", "model": "gpt-4o-mini", "apikey": masked},
    )
    cfg = await admin_services.get_audit_llm_config(db_session)
    assert cfg["model"] == "gpt-4o-mini"
    assert cfg["apikey"] == "sk-old-key-9999"  # 旧 key 保留


async def test_audit_llm_db_overrides_env_for_build_guard(
    admin_client: httpx.AsyncClient, db_session, monkeypatch
) -> None:
    """DB 配置优先于 env：build_guard 用 DB 的 model 而非 settings.audit_model。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "audit_model", "env-model-should-not-win")
    await _put_audit(
        admin_client,
        {"enabled": True, "provider": "openai", "model": "db-model-wins", "apikey": "sk-k"},
    )
    g = await guard.build_guard(
        type("C", (), {"s": db_session})()  # 最小 ctx：只需 .s
    )
    assert isinstance(g, guard.Guard)
    assert g._model == "db-model-wins"  # noqa: SLF001 测试断言内部字段


async def test_audit_llm_disabled_returns_noop(admin_client: httpx.AsyncClient, db_session) -> None:
    await _put_audit(
        admin_client,
        {"enabled": False, "provider": "openai", "model": "m", "apikey": "sk-k"},
    )
    g = await guard.build_guard(type("C", (), {"s": db_session})())
    assert isinstance(g, guard.NoopGuard)


async def test_audit_llm_window_fields_roundtrip_and_keep(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    """滑窗参数 PUT 落库回显；再次 PUT 不带（None）→ 保留旧值。"""
    body = {
        "enabled": True,
        "provider": "openai_compat",
        "model": "qwen-plus",
        "apikey": "sk-win-1",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }
    await _put_audit(
        admin_client,
        {**body, "interval_ms": 120_000, "min_chars_between": 120, "max_buffer_chars": 800},
    )
    cfg = await admin_services.get_audit_llm_config(db_session)
    assert (cfg["interval_ms"], cfg["min_chars_between"], cfg["max_buffer_chars"]) == (
        120_000,
        120,
        800,
    )

    await _put_audit(admin_client, body)  # 不带窗口字段
    cfg = await admin_services.get_audit_llm_config(db_session)
    assert cfg["interval_ms"] == 120_000  # 旧值保留
    assert cfg["min_chars_between"] == 120
    assert cfg["max_buffer_chars"] == 800

    g = await guard.build_guard(type("C", (), {"s": db_session})())
    assert (g.interval_ms, g.min_chars_between, g.max_buffer_chars) == (120_000, 120, 800)


async def test_audit_llm_window_fields_validation(
    admin_client: httpx.AsyncClient,
) -> None:
    """interval_ms 下界 100ms：过小值直接拒绝（防止每个 chunk 都触发审核）。"""
    r = await admin_client.put(
        "/api/v1/admin/settings",
        json={
            **_BASE_BODY,
            "audit_llm": {"enabled": True, "provider": "openai", "model": "m", "interval_ms": 1},
        },
    )
    assert r.status_code == 400  # 请求校验失败统一映射 400（非 FastAPI 默认 422）


async def test_audit_llm_config_hot_reload_within_same_session(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    """回归：同一 session 二次读取必须看到 admin 更新。

    worker 整个 run 复用一个 session（expire_on_commit=False），若 get_audit_llm_config
    用 db.get 会命中 identity map 旧快照，admin 改配置对进行中的 run 永不生效。
    """
    body = {"enabled": True, "provider": "openai", "apikey": "sk-hot-1"}
    await _put_audit(admin_client, {**body, "model": "m1"})
    cfg1 = await admin_services.get_audit_llm_config(db_session)
    assert cfg1["model"] == "m1"

    await _put_audit(admin_client, {**body, "model": "m2"})  # 另一 session 更新
    cfg2 = await admin_services.get_audit_llm_config(db_session)  # 同一 session 再读
    assert cfg2["model"] == "m2"


async def test_audit_llm_test_endpoint_admin_only(
    auth_client: httpx.AsyncClient,
) -> None:
    r = await auth_client.post(
        "/api/v1/admin/settings/audit-llm/test",
        json={"enabled": True, "provider": "openai", "model": "m", "apikey": "sk-k"},
    )
    assert r.status_code == 403


async def test_audit_llm_test_endpoint_uses_form_values(
    admin_client: httpx.AsyncClient, monkeypatch
) -> None:
    """测试端点用表单当前值 dry-test（mock test_connectivity 防真实付费调用）。"""
    from app.llm import provider as llm_provider

    captured: dict = {}

    async def _fake_connectivity(prov, apikey, model, base_url=None):
        captured.update(provider=prov, apikey=apikey, model=model, base_url=base_url)
        return True, None

    monkeypatch.setattr(llm_provider, "test_connectivity", _fake_connectivity)
    r = await admin_client.post(
        "/api/v1/admin/settings/audit-llm/test",
        json={
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apikey": "sk-form-value",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["tested_ok"] is True
    assert captured["apikey"] == "sk-form-value"
    assert captured["model"] == "gpt-4o-mini"


async def test_audit_llm_test_falls_back_to_stored_key(
    admin_client: httpx.AsyncClient, monkeypatch
) -> None:
    """apikey 传 masked/空 → 用 DB 已存 key 测试（改 model 不重填 key 也能测）。"""
    from app.llm import provider as llm_provider

    await _put_audit(
        admin_client,
        {"enabled": True, "provider": "openai", "model": "gpt-4o", "apikey": "sk-stored-777"},
    )
    captured: dict = {}

    async def _fake_connectivity(prov, apikey, model, base_url=None):
        captured.update(apikey=apikey, model=model)
        return True, None

    monkeypatch.setattr(llm_provider, "test_connectivity", _fake_connectivity)
    r = await admin_client.post(
        "/api/v1/admin/settings/audit-llm/test",
        json={
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4o-mini",
            "apikey": "sk-***777",  # masked 形态
        },
    )
    assert r.status_code == 200, r.text
    assert captured["apikey"] == "sk-stored-777"  # 回退 DB 已存 key
    assert captured["model"] == "gpt-4o-mini"  # model 用表单新值
