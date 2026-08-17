from pathlib import Path

import pytest

from app.core.errors import AppError
from app.sandbox.base import BuildResult
from app.sandbox.paths import resolve_workspace_rel
from app.sandbox.resources import TIER_LIMITS, docker_log_host_config, tier_limits


def test_build_result_carries_failure_kind() -> None:
    r = BuildResult(ok=False, error="docker error", failure_kind="infra")
    assert r.failure_kind == "infra"


def test_tier_limits_single_source() -> None:
    assert set(TIER_LIMITS) == {"lite", "standard", "heavy"}
    assert tier_limits("heavy")["timeout_s"] == 120
    assert tier_limits("unknown")["timeout_s"] == tier_limits("standard")["timeout_s"]


def test_docker_log_host_config_log_rotation() -> None:
    cfg = docker_log_host_config()
    assert cfg["AutoRemove"] is False
    assert cfg["LogConfig"]["Type"] == "json-file"


def test_resolve_workspace_rel_blocks_traversal(tmp_path: Path) -> None:
    with pytest.raises(AppError):
        resolve_workspace_rel(tmp_path, "../secret")
    target = resolve_workspace_rel(tmp_path, "a/b.html")
    assert target == (tmp_path / "a" / "b.html").resolve()
