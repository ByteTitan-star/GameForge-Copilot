"""路由 smoke：仅剩 healthz（其余端点均有专项测试）。"""

import httpx
import pytest

# (method, path, json body, expected status, is paginated)
CASES: list[tuple[str, str, dict | None, int, bool]] = [
    ("GET", "/healthz", None, 200, False),
]


@pytest.mark.parametrize(
    ("method", "path", "body", "status", "paginated"),
    CASES,
    ids=[c[1].split("?")[0] for c in CASES],
)
async def test_route_smoke(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    body: dict | None,
    status: int,
    paginated: bool,
) -> None:
    url = path
    resp = await client.request(method, url, json=body)
    assert resp.status_code == status, f"{method} {url} -> {resp.status_code}: {resp.text}"
    if status == 204:
        assert resp.text == ""
        return
    data = resp.json()
    assert "data" in data, f"{method} {url} 缺少 data: {data}"
    if paginated:
        for k in ("total", "page", "size"):
            assert k in data
        assert isinstance(data["data"], list)
