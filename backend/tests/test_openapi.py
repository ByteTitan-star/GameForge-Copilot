"""OpenAPI 快照与契约路径覆盖测试。

防回归：后端 schema/路由改动后，导出的 openapi 必须与 contracts/openapi.json
快照一致（contracts/README.md CI 校验项之一）。
"""

import json
from pathlib import Path

from app.export_openapi import export

REPO = Path(__file__).resolve().parents[2]
CONTRACT_OPENAPI = REPO / "contracts" / "openapi.json"

# docs/10 §4 + INTEGRATION 列出的全部 HTTP 端点（WS 不进 OpenAPI，单独由 §5 约束）
REQUIRED_PATHS = {
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/verify-email",
    "/api/v1/auth/password/reset",
    "/api/v1/auth/password/reset/confirm",
    "/api/v1/auth/password/change",
    "/api/v1/auth/logout",
    "/api/v1/me/llm-configs",
    "/api/v1/me/llm-configs/test",
    "/api/v1/me/llm-configs/{config_id}",
    "/api/v1/me/llm-configs/{config_id}/test",
    "/api/v1/me/usage",
    "/api/v1/me/notifications",
    "/api/v1/admin/usage",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/games",
    "/api/v1/admin/settings",
    "/api/v1/admin/settings/audit-llm/test",
    "/api/v1/games",
    "/api/v1/games/{game_id}",
    "/api/v1/games/{game_id}/versions",
    "/api/v1/games/{game_id}/runs",
    "/api/v1/games/{game_id}/messages",
    "/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve",
    "/api/v1/games/{game_id}/publish/submit",
    "/api/v1/games/{game_id}/take-down",
    "/api/v1/runs/{run_id}",
    "/api/v1/runs/{run_id}/pause",
    "/api/v1/runs/{run_id}/resume",
    "/api/v1/runs/{run_id}/cancel",
    "/api/v1/publish/queue",
    "/api/v1/publish/{publish_request_id}/approve",
    "/api/v1/publish/{publish_request_id}/reject",
}


def test_export_is_valid_json() -> None:
    spec = json.loads(export())
    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] == "GameForge-Copilot"


def test_export_covers_contract_paths() -> None:
    spec = json.loads(export())
    paths = set(spec["paths"].keys())
    missing = REQUIRED_PATHS - paths
    assert not missing, f"openapi 缺少契约路径: {sorted(missing)}"


def test_snapshot_matches_committed() -> None:
    """导出快照必须与仓库 contracts/openapi.json 一致，不一致说明忘记刷新快照。"""
    assert CONTRACT_OPENAPI.exists(), "contracts/openapi.json 不存在"
    committed = json.loads(CONTRACT_OPENAPI.read_text(encoding="utf-8"))
    exported = json.loads(export())
    assert exported == committed, "contracts/openapi.json 与 app 导出不一致，请重跑 export_openapi"
