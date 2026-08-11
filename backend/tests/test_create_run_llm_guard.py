"""create_run 默认 LLM 配置前置校验。

未配置默认 LLM → 400 LLM_CONFIG_INVALID（run 不入队）；
有默认配置 → 正常 201；
显式传不存在的 llm_config_id → 404 LLM_CONFIG_NOT_FOUND（回归保护既有逻辑）。
"""

import uuid

import httpx

GAME_BODY = {"title": "测试游戏", "requirement": "做一个贪吃蛇"}


async def _login_verified_without_llm(
    client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    """注册→验证→登录一个无 LLM 配置的已验证用户，Authorization 头就位。"""
    email = "nollm@b.com"
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password123"}
    )
    code = sent[f"verify:{email}"]
    r = await client.post("/api/v1/auth/verify-email", json={"email": email, "code": code})
    assert r.status_code == 200, r.text
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password123"}
    )
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['data']['access_token']}"


async def test_create_run_rejected_when_no_default_llm(
    client: httpx.AsyncClient, sent: dict[str, str]
) -> None:
    """已验证但未配置任何 LLM → 发 run 返回 400 LLM_CONFIG_INVALID。"""
    await _login_verified_without_llm(client, sent)
    gid = (await client.post("/api/v1/games", json=GAME_BODY)).json()["data"]["game_id"]
    r = await client.post(f"/api/v1/games/{gid}/runs", json={"requirement": "贪吃蛇"})
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "LLM_CONFIG_INVALID"


async def test_create_run_ok_when_default_llm_exists(
    verified_client: httpx.AsyncClient,
) -> None:
    """有默认 LLM 配置（verified_client 预置）→ 发 run 正常 201。"""
    gid = (await verified_client.post("/api/v1/games", json=GAME_BODY)).json()["data"][
        "game_id"
    ]
    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs", json={"requirement": "贪吃蛇"}
    )
    assert r.status_code == 201, r.text


async def test_create_run_explicit_id_not_found(
    verified_client: httpx.AsyncClient,
) -> None:
    """显式传不存在的 llm_config_id → 404 LLM_CONFIG_NOT_FOUND（回归保护）。"""
    gid = (await verified_client.post("/api/v1/games", json=GAME_BODY)).json()["data"][
        "game_id"
    ]
    r = await verified_client.post(
        f"/api/v1/games/{gid}/runs",
        json={"requirement": "贪吃蛇", "llm_config_id": str(uuid.uuid4())},
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "LLM_CONFIG_NOT_FOUND"
