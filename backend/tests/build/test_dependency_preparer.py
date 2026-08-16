"""DependencyPreparer 单元测试（mock builder，不跑真实 pnpm）。"""

from pathlib import Path

import pytest

from app.forge.build.dependency_preparer import DependencyPreparer
from app.forge.build.profile import BuildProfile
from app.sandbox.builder import BuilderRunResult, shell_cmd


class RecordingBuilder:
    def __init__(self, result: BuilderRunResult) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def run(self, workspace: Path, cmd, *, network_mode: str, store_readonly: bool):
        self.calls.append(
            {
                "workspace": workspace,
                "cmd": list(cmd),
                "network_mode": network_mode,
                "store_readonly": store_readonly,
            }
        )
        if self.result.ok:
            (workspace / "pnpm-lock.yaml").write_text("lockfile: 1\n", encoding="utf-8")
        return self.result


@pytest.mark.asyncio
async def test_prepare_cache_hit_skips_builder(tmp_path: Path) -> None:
    profile = BuildProfile()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "pnpm-workspace.yaml").write_text("allowBuilds: {}\n", encoding="utf-8")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfile: 1\n", encoding="utf-8")

    from app.sandbox.builder import prepare_cache_key

    key = prepare_cache_key(tmp_path, profile)
    (tmp_path / ".prepare-cache-key").write_text(key, encoding="utf-8")

    builder = RecordingBuilder(BuilderRunResult(ok=True))
    result = await DependencyPreparer(builder=builder).prepare(tmp_path, profile)

    assert result.ok
    assert result.skipped
    assert result.logs == "prepare cache hit"
    assert builder.calls == []


@pytest.mark.asyncio
async def test_prepare_success_writes_marker_and_profile(tmp_path: Path) -> None:
    profile = BuildProfile(builder_version="v9")
    (tmp_path / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
    (tmp_path / "pnpm-workspace.yaml").write_text("allowBuilds: {}\n", encoding="utf-8")

    builder = RecordingBuilder(BuilderRunResult(ok=True, logs="fetched"))
    result = await DependencyPreparer(builder=builder).prepare(tmp_path, profile)

    assert result.ok
    assert not result.skipped
    assert result.cache_key
    assert (tmp_path / ".prepare-cache-key").read_text(encoding="utf-8") == result.cache_key
    assert (tmp_path / "build-profile.json").is_file()
    assert (tmp_path / "pnpm-lock.yaml").is_file()
    assert builder.calls[0]["network_mode"] == "bridge"
    assert builder.calls[0]["store_readonly"] is False
    script = builder.calls[0]["cmd"]
    assert script[0] == "sh" and "--lockfile-only" in script[2]


@pytest.mark.asyncio
async def test_prepare_failure_propagates_error(tmp_path: Path) -> None:
    profile = BuildProfile()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    builder = RecordingBuilder(BuilderRunResult(ok=False, logs="npm down", error="构建退出码 1"))
    result = await DependencyPreparer(builder=builder).prepare(tmp_path, profile)

    assert not result.ok
    assert result.error == "构建退出码 1"
    assert result.logs == "npm down"
    assert not (tmp_path / ".prepare-cache-key").exists()


@pytest.mark.asyncio
async def test_prepare_install_shell_passed_to_builder(tmp_path: Path) -> None:
    profile = BuildProfile()
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    builder = RecordingBuilder(BuilderRunResult(ok=True))
    await DependencyPreparer(builder=builder).prepare(tmp_path, profile)

    shell = builder.calls[0]["cmd"][2]
    assert "fetch" in shell
    assert shell_cmd(shell) == builder.calls[0]["cmd"]
