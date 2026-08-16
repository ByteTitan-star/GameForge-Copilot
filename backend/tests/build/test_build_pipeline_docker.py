"""§26 Docker 集成测试：网络隔离 + 固定 demo 真构建（需 RUN_BUILD_PIPELINE=1）。"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from app.forge.build import BuildPipeline
from app.sandbox.builder import DockerBuilder, shell_cmd


def _docker_available() -> bool:
    return shutil.which("docker") is not None and os.getenv("RUN_BUILD_PIPELINE") == "1"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_builder_network_isolated() -> None:
    """§26.3：NetworkMode=none 时容器内无法访问外网。"""
    if not _docker_available():
        pytest.skip("needs RUN_BUILD_PIPELINE=1 and docker daemon")

    builder = DockerBuilder()
    with tempfile.TemporaryDirectory() as ws:
        # fetch 失败 → exit 0；能连上外网 → exit 1
        probe = (
            "node -e "
            "\"fetch('https://example.com')"
            ".then(()=>process.exit(1))"
            '.catch(()=>process.exit(0))"'
        )
        result = await builder.run(
            Path(ws),
            shell_cmd(probe),
            network_mode="none",
            store_readonly=True,
        )
    assert result.ok, result.error or result.logs


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_vite_ts_offline_build() -> None:
    if not _docker_available():
        pytest.skip("needs RUN_BUILD_PIPELINE=1 and docker daemon")

    result = await BuildPipeline().run_vite_ts_demo()
    assert result.ok, result.error or result.logs
    assert "index.html" in result.dist
    assert "pnpm-lock.yaml" in result.build_snapshot


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_react_demo_build() -> None:
    if not _docker_available():
        pytest.skip("needs RUN_BUILD_PIPELINE=1 and docker daemon")

    result = await BuildPipeline().run_react_demo()
    assert result.ok, result.error or result.logs
    assert "index.html" in result.dist


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_phaser_matter_demo_build() -> None:
    if not _docker_available():
        pytest.skip("needs RUN_BUILD_PIPELINE=1 and docker daemon")

    result = await BuildPipeline().run_phaser_matter_demo()
    assert result.ok, result.error or result.logs
    assert "index.html" in result.dist
