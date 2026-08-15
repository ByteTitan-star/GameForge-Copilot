"""构建链 P1：模板加载 / collect / builder / preparer / pipeline。"""

import os
from pathlib import Path

import pytest

from app.core.errors import AppError, ErrorCode
from app.forge.build import (
    BuildPipeline,
    default_build_profile,
    load_vite_ts_template_files,
    vite_ts_template_dir,
)
from app.forge.build.constants import BUILD_SNAPSHOT_FILES, BUILDER_ALLOWED_BUILDS
from app.forge.build.profile import BuildProfile
from app.forge.build.template import repo_root
from app.sandbox.collect import collect_artifact_files
from app.sandbox.local import LocalSandbox


def test_vite_ts_template_has_required_files() -> None:
    files = load_vite_ts_template_files()
    assert "package.json" in files
    assert "vite.config.ts" in files
    assert "pnpm-workspace.yaml" in files
    assert "src/main.ts" in files
    assert "pnpm-lock.yaml" not in files
    assert "./" in files["vite.config.ts"]


def test_build_profile_roundtrip() -> None:
    profile = default_build_profile()
    restored = BuildProfile.from_json(profile.to_json())
    assert restored == profile


def test_collect_root_dist(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html></html>", encoding="utf-8")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_bytes(b"console.log(1)")
    files = collect_artifact_files(tmp_path, collect_root="dist")
    assert set(files) == {"index.html", "assets/app.js"}


def test_collect_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(AppError) as exc:
        collect_artifact_files(tmp_path, collect_root="dist")
    assert exc.value.code == ErrorCode.SANDBOX_FAILED


def test_collect_quota_exceeded(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(AppError) as exc:
        collect_artifact_files(tmp_path, collect_root="dist", max_size_mb=1)
    assert exc.value.code == ErrorCode.QUOTA_EXCEEDED


def test_builder_allowed_builds_includes_esbuild() -> None:
    assert BUILDER_ALLOWED_BUILDS.get("esbuild") is True


def test_build_snapshot_files_include_lockfile() -> None:
    assert "pnpm-lock.yaml" in BUILD_SNAPSHOT_FILES
    assert "build-profile.json" in BUILD_SNAPSHOT_FILES


def test_repo_root_contains_docker_templates() -> None:
    root = repo_root()
    assert (root / "docker" / "templates" / "vite-ts" / "package.json").is_file()


def test_vite_ts_template_skips_build_artifacts() -> None:
    files = load_vite_ts_template_files()
    assert not any("node_modules" in k for k in files)
    assert not any(k.startswith("dist/") for k in files)
    assert "README.md" not in files


@pytest.mark.asyncio
async def test_local_sandbox_collect_root_dist() -> None:
    r = await LocalSandbox().execute(
        source={"dist/index.html": "<html>ok</html>"},
        collect_root="dist",
    )
    assert r.ok
    assert r.files["index.html"] == b"<html>ok</html>"


@pytest.mark.integration
def test_vite_ts_template_dir_exists() -> None:
    assert vite_ts_template_dir().is_dir()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_p1_vite_ts_demo_build_docker() -> None:
    if os.getenv("RUN_BUILD_PIPELINE") != "1":
        pytest.skip("set RUN_BUILD_PIPELINE=1 with docker + gameforge-builder:v1")

    result = await BuildPipeline().run_vite_ts_demo()
    assert result.ok, result.error or result.logs
    assert "index.html" in result.dist
    assert "pnpm-lock.yaml" in result.build_snapshot
    html = result.dist["index.html"].decode("utf-8")
    assert "./assets/" in html or 'src="./assets/' in html


@pytest.mark.integration
@pytest.mark.asyncio
async def test_p1_vite_ts_demo_build_local(monkeypatch: pytest.MonkeyPatch) -> None:
    if os.getenv("RUN_BUILD_PIPELINE") != "local":
        pytest.skip("set RUN_BUILD_PIPELINE=local with pnpm 11+ and Node")

    monkeypatch.setattr("app.core.config.settings.builder_backend", "local")
    result = await BuildPipeline().run_vite_ts_demo()
    assert result.ok, result.error or result.logs
    assert "index.html" in result.dist
    assert "pnpm-lock.yaml" in result.build_snapshot
