"""视觉验收模型（#160）admin 后台配置测试：加密写入、masked 回显、DB 优先 env、带图探针端点。"""

import httpx

from app.admin import services as admin_services
from app.llm import provider as llm_provider

_BASE_BODY = {
    "default_daily_token_limit": 500_000,
    "default_monthly_token_limit": 10_000_000,
    "default_rate_limit_per_min": 30,
    "admin_contact_email": "",
}

_VISUAL = {
    "enabled": True,
    "provider": "openai_compat",
    "model": "glm-5.3-flash",
    "apikey": "sk-visual-test-123456",
    "base_url": "https://open.bigmodel.cn/api/paas/v4",
}


async def _put_visual(admin_client: httpx.AsyncClient, visual: dict) -> dict:
    r = await admin_client.put("/api/v1/admin/settings", json={**_BASE_BODY, "visual_llm": visual})
    assert r.status_code == 200, r.text
    return r.json()["data"]["visual_llm"]


async def test_visual_llm_unconfigured_by_default(
    admin_client: httpx.AsyncClient, db_session, monkeypatch
) -> None:
    """无 DB 行、env 为空 → model/apikey 皆空（forge 侧据此整体跳过视觉验收）。"""
    from app.core.config import settings

    monkeypatch.setattr(settings, "visual_acceptance_model", "")
    monkeypatch.setattr(settings, "visual_acceptance_apikey", "")
    cfg = await admin_services.get_visual_llm_config(db_session)
    assert cfg["model"] == "" and cfg["apikey"] == ""
    r = await admin_client.get("/api/v1/admin/settings")
    assert r.json()["data"]["visual_llm"]["apikey"] == ""


async def test_visual_llm_write_encrypt_and_masked_echo(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    await _put_visual(admin_client, _VISUAL)
    cfg = await admin_services.get_visual_llm_config(db_session)
    assert cfg["model"] == "glm-5.3-flash"
    assert cfg["apikey"] == "sk-visual-test-123456"
    assert cfg["base_url"] == "https://open.bigmodel.cn/api/paas/v4"

    r = await admin_client.get("/api/v1/admin/settings")
    visual = r.json()["data"]["visual_llm"]
    assert visual["apikey"].startswith("sk-") and "***" in visual["apikey"]
    assert "sk-visual-test-123456" not in visual["apikey"]


async def test_visual_llm_keep_old_key_when_masked(
    admin_client: httpx.AsyncClient, db_session
) -> None:
    await _put_visual(admin_client, {**_VISUAL, "apikey": "sk-old-key-9999"})
    r = await admin_client.get("/api/v1/admin/settings")
    masked = r.json()["data"]["visual_llm"]["apikey"]
    await _put_visual(admin_client, {**_VISUAL, "model": "gpt-4o", "apikey": masked})
    cfg = await admin_services.get_visual_llm_config(db_session)
    assert cfg["model"] == "gpt-4o"
    assert cfg["apikey"] == "sk-old-key-9999"


async def test_visual_llm_db_overrides_env(
    admin_client: httpx.AsyncClient, db_session, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "visual_acceptance_model", "env-model-should-not-win")
    await _put_visual(admin_client, {**_VISUAL, "model": "db-model-wins"})
    cfg = await admin_services.get_visual_llm_config(db_session)
    assert cfg["model"] == "db-model-wins"


async def test_visual_llm_test_endpoint_uses_vision_probe(
    admin_client: httpx.AsyncClient, monkeypatch
) -> None:
    """端点必须走带图探针（test_vision_connectivity），而不是纯文本 test_connectivity。"""
    calls: list[tuple] = []

    async def _fake_vision(prov, apikey, model, base_url=None):
        calls.append((prov.value, apikey, model, base_url))
        return True, None

    async def _must_not_call(*a, **k):
        raise AssertionError("text-only connectivity probe must not be used for vision model")

    monkeypatch.setattr(llm_provider, "test_vision_connectivity", _fake_vision)
    monkeypatch.setattr(llm_provider, "test_connectivity", _must_not_call)
    r = await admin_client.post("/api/v1/admin/settings/visual-llm/test", json=_VISUAL)
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"tested_ok": True, "error": None}
    assert calls == [
        ("openai_compat", "sk-visual-test-123456", "glm-5.3-flash", _VISUAL["base_url"])
    ]


async def test_visual_llm_test_endpoint_falls_back_to_saved_key(
    admin_client: httpx.AsyncClient, monkeypatch
) -> None:
    """表单 apikey 为 masked → 用 DB 已存明文 key 探测。"""
    await _put_visual(admin_client, {**_VISUAL, "apikey": "sk-saved-777"})
    seen: list[str] = []

    async def _fake_vision(prov, apikey, model, base_url=None):
        seen.append(apikey)
        return False, "模型未能读取图片内容"

    monkeypatch.setattr(llm_provider, "test_vision_connectivity", _fake_vision)
    r = await admin_client.post(
        "/api/v1/admin/settings/visual-llm/test", json={**_VISUAL, "apikey": "sk-***777"}
    )
    assert r.status_code == 200
    assert r.json()["data"]["tested_ok"] is False
    assert "图片" in r.json()["data"]["error"]
    assert seen == ["sk-saved-777"]


async def test_vision_probe_rejects_text_only_answer(monkeypatch) -> None:
    """模型没看图（答非所问）→ 探针判失败；答出 light → 通过。"""
    from app.enums import LLMProvider

    answers = iter(["I cannot see any image.", "light"])

    async def _fake_complete(*a, **k):
        return llm_provider.LLMCompletion(content=next(answers), usage=llm_provider.Usage())

    monkeypatch.setattr(llm_provider, "complete", _fake_complete)
    ok, err = await llm_provider.test_vision_connectivity(
        LLMProvider.OPENAI_COMPAT, "k", "m", "https://x.example/v1"
    )
    assert ok is False and err and "图片" in err
    ok, err = await llm_provider.test_vision_connectivity(
        LLMProvider.OPENAI_COMPAT, "k", "m", "https://x.example/v1"
    )
    assert (ok, err) == (True, None)
