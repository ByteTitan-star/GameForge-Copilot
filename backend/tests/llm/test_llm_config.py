"""M2 LLM 配置：CRUD + 连通测试 + 加密掩码 + ownership/默认互斥。

provider.test_connectivity 被 monkeypatch，不打真实网络。
"""

import httpx
import pytest
from app.llm import provider

BASE = "/api/v1/me/llm-configs"
_BODY = {"provider": "anthropic", "model": "claude-sonnet-5", "apikey": "sk-test-1234567890"}


async def _ok(_provider, _apikey, _model, _base_url=None) -> tuple[bool, str | None]:
    return True, None


async def _fail(_provider, _apikey, _model, _base_url=None) -> tuple[bool, str | None]:
    return False, "HTTP 401"


async def test_create_list_mask_default(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    r = await auth_client.post(BASE, json={**_BODY, "is_default": True})
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["tested_ok"] is True
    assert d["is_default"] is True
    assert d["apikey_masked"].startswith("sk-") and "***" in d["apikey_masked"]

    # list 含此配置
    r = await auth_client.get(BASE)
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["config_id"] == d["config_id"]


async def test_create_second_default_unsets_first(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    r1 = await auth_client.post(BASE, json={**_BODY, "is_default": True})
    id1 = r1.json()["data"]["config_id"]
    # 第二个 default
    r2 = await auth_client.post(BASE, json={**_BODY, "model": "claude-opus", "is_default": True})
    id2 = r2.json()["data"]["config_id"]

    r = await auth_client.get(BASE)
    by_id = {it["config_id"]: it for it in r.json()["data"]}
    assert by_id[id1]["is_default"] is False
    assert by_id[id2]["is_default"] is True


async def test_patch_model_and_default(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    r = await auth_client.post(BASE, json={**_BODY, "is_default": False})
    cid = r.json()["data"]["config_id"]

    r = await auth_client.patch(f"{BASE}/{cid}", json={"model": "claude-opus"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["model"] == "claude-opus"


async def test_test_endpoint(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    r = await auth_client.post(BASE, json=_BODY)
    cid = r.json()["data"]["config_id"]

    r = await auth_client.post(f"{BASE}/{cid}/test")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["tested_ok"] is True
    assert d["error"] is None


async def test_draft_test_endpoint(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    r = await auth_client.post(f"{BASE}/test", json=_BODY)
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["tested_ok"] is True
    assert d["error"] is None


async def test_draft_test_fail_returns_error_not_400(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _fail)
    r = await auth_client.post(f"{BASE}/test", json=_BODY)
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["tested_ok"] is False
    assert d["error"] == "HTTP 401"


async def test_saved_test_passes_model_and_base_url(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple] = []

    async def _spy(provider, apikey, model, base_url=None):
        calls.append((provider, apikey, model, base_url))
        return True, None

    monkeypatch.setattr(provider, "test_connectivity", _spy)
    body = {
        **_BODY,
        "base_url": "https://proxy.example.com/v1",
    }
    r = await auth_client.post(BASE, json=body)
    cid = r.json()["data"]["config_id"]

    r = await auth_client.post(f"{BASE}/{cid}/test")
    assert r.status_code == 200
    assert len(calls) == 2
    assert calls[-1][2] == "claude-sonnet-5"
    assert calls[-1][3] == "https://proxy.example.com/v1"


async def test_create_connectivity_fail_not_saved(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _fail)
    r = await auth_client.post(BASE, json=_BODY)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "LLM_CONFIG_INVALID"
    # 未保存
    r = await auth_client.get(BASE)
    assert r.json()["data"] == []


async def test_delete_default_conflict_and_non_default_ok(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    # 两个配置，第一个 default
    r1 = await auth_client.post(BASE, json={**_BODY, "is_default": True})
    id_default = r1.json()["data"]["config_id"]
    r2 = await auth_client.post(BASE, json={**_BODY, "model": "gpt-4o"})
    id_other = r2.json()["data"]["config_id"]

    # 删除 default（还有另一个）→ 409
    r = await auth_client.delete(f"{BASE}/{id_default}")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_STATE"

    # 删非 default → 200
    r = await auth_client.delete(f"{BASE}/{id_other}")
    assert r.status_code == 200
    assert r.json()["data"]["deleted"] is True


async def test_requires_auth(client: httpx.AsyncClient) -> None:
    """me-scoped 端点未登录 → 401。"""
    r = await client.get(BASE)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHORIZED"


async def test_compat_requires_base_url() -> None:
    """openai_compat 无 base_url → 连通测试失败（#9 修复）。"""
    from app.enums import LLMProvider as P
    from app.llm.provider import test_connectivity

    ok, err = await test_connectivity(P.OPENAI_COMPAT, "sk", "gpt-4o")
    assert not ok
    assert err and "base_url" in err


async def test_empty_model_rejected() -> None:
    from app.enums import LLMProvider as P
    from app.llm.provider import test_connectivity

    ok, err = await test_connectivity(P.OPENAI, "sk", "   ")
    assert not ok
    assert err and "model" in err


def test_normalize_base_url_strips_completion_suffix() -> None:
    from app.enums import LLMProvider as P
    from app.llm.provider import _api_base

    base = _api_base(P.OPENAI, "https://api.openai.com/v1/chat/completions")
    assert base == "https://api.openai.com/v1"


def test_normalize_base_url_appends_v1_for_host_only() -> None:
    from app.enums import LLMProvider as P
    from app.llm.provider import _api_base

    base = _api_base(P.OPENAI_COMPAT, "https://api.deepseek.com")
    assert base == "https://api.deepseek.com/v1"


def test_official_anthropic_base_uses_messages_endpoint() -> None:
    from app.enums import LLMProvider as P
    from app.llm.provider import _auth_headers, _messages_url

    assert _messages_url(P.ANTHROPIC, None) == "https://api.anthropic.com/v1/messages"
    assert "x-api-key" in _auth_headers(P.ANTHROPIC, "sk-test", None)


async def test_not_found_404(
    auth_client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provider, "test_connectivity", _ok)
    fake_id = "00000000-0000-4000-8000-000000000099"
    r = await auth_client.patch(f"{BASE}/{fake_id}", json={"model": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "LLM_CONFIG_NOT_FOUND"
