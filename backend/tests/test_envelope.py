import httpx

from app.core.response import ApiResponse


async def test_healthz(client: httpx.AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"data": {"status": "ok"}}


async def test_success_envelope_shape(client: httpx.AsyncClient) -> None:
    """所有成功响应外层必须是 {"data": ...}。"""
    resp = await client.get("/healthz")
    body = resp.json()
    assert "data" in body
    assert set(body.keys()) == {"data"}
    # ApiResponse 模型本身保证 data 字段存在
    ApiResponse.model_validate(body)
