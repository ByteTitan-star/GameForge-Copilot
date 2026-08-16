import httpx

from app.core.errors import CODE_TO_STATUS, ErrorCode

# docs/10 §3 错误码 → HTTP 表
EXPECTED = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.EMAIL_NOT_VERIFIED: 403,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.QUOTA_EXCEEDED: 429,
    ErrorCode.LLM_CONFIG_INVALID: 400,
    ErrorCode.GAME_NOT_FOUND: 404,
    ErrorCode.INVALID_STATE: 409,
    ErrorCode.SANDBOX_FAILED: 500,
    ErrorCode.VALIDATION_ERROR: 400,
    ErrorCode.EMAIL_TAKEN: 409,
}


def test_error_code_status_mapping() -> None:
    """错误码 → HTTP 状态码必须与契约 docs/10 §3 一致。"""
    for code, status in EXPECTED.items():
        assert CODE_TO_STATUS[code.value] == status, f"{code} 映射不一致"


async def test_validation_error_envelope(client: httpx.AsyncClient) -> None:
    """入参校验失败 → 400 {"error": {code: VALIDATION_ERROR, ...}}。"""
    resp = await client.post("/api/v1/auth/refresh", json={})
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["message"]
    assert "errors" in err["detail"]
