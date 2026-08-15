"""builder 模块单元测试：shell 拼装 / cache key / get_builder。"""

import os
from pathlib import Path

import pytest

from app.forge.build.profile import BuildProfile
from app.sandbox.builder import (
    DockerBuilder,
    LocalBuilder,
    corepack_activate_shell,
    get_builder,
    offline_install_shell,
    pin_docker_pnpm,
    pnpm_cli,
    pnpm_setup_shell,
    prepare_cache_key,
    prepare_install_shell,
    resolve_store_path,
    shell_cmd,
    write_build_profile,
)


def test_shell_cmd_wraps_script() -> None:
    assert shell_cmd("echo hi") == ["sh", "-c", "echo hi"]


def test_pin_docker_pnpm_replaces_cli_tokens() -> None:
    shell = (
        "pnpm config set cache-dir '/workspace/.build-cache' && "
        "pnpm install --offline && pnpm build"
    )
    pinned = pin_docker_pnpm(shell)
    assert pinned.count("/usr/local/bin/pnpm") == 3
    assert "/workspace/.build-cache" in pinned
    assert ".usr/local/bin/pnpm" not in pinned
    assert " pnpm " not in pinned


def test_pnpm_cli_platform_specific() -> None:
    if os.name == "nt":
        assert pnpm_cli() == "corepack pnpm"
    else:
        assert pnpm_cli() == "pnpm"


def test_offline_install_shell_has_frozen_flags() -> None:
    shell = offline_install_shell("pnpm config set store-dir /store")
    assert "--offline" in shell
    assert "--frozen-lockfile" in shell
    assert "--frozen-store" in shell
    assert "--trust-lockfile" in shell
    assert shell.endswith(f"{pnpm_cli()} build")


def test_prepare_install_shell_has_lockfile_only_and_fetch() -> None:
    shell = prepare_install_shell("setup")
    assert "--lockfile-only" in shell
    assert "fetch" in shell


def test_pnpm_setup_shell_unix_style(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(os, "name", "posix")
    shell = pnpm_setup_shell(store_dir="/pnpm/store", workspace=tmp_path)
    assert "pnpm config set registry" in shell
    assert "store-dir '/pnpm/store'" in shell
    assert f"cache-dir '{tmp_path / '.build-cache'}'" in shell
    assert "corepack" not in shell


def test_pnpm_setup_shell_windows_uses_corepack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "nt")
    (tmp_path / "package.json").write_text(
        '{"packageManager":"pnpm@11.21.0"}',
        encoding="utf-8",
    )
    shell = pnpm_setup_shell(store_dir=str(tmp_path / "store"), workspace=tmp_path)
    assert "corepack prepare pnpm@11.21.0" in shell
    assert "corepack pnpm config set registry" in shell
    assert f'store-dir "{tmp_path / "store"}"' in shell


def test_corepack_activate_shell_empty_on_unix(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "posix")
    assert corepack_activate_shell(tmp_path) == ""


def test_corepack_activate_shell_reads_package_manager(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(os, "name", "nt")
    (tmp_path / "package.json").write_text(
        '{"packageManager":"pnpm@9.0.0"}',
        encoding="utf-8",
    )
    assert corepack_activate_shell(tmp_path) == "corepack prepare pnpm@9.0.0 --activate && "


def test_resolve_store_path_creates_relative_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    store = resolve_store_path(".test-store")
    assert store.is_dir()
    assert store == (tmp_path / ".test-store").resolve()


def test_prepare_cache_key_stable(tmp_path: Path) -> None:
    profile = BuildProfile()
    (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
    (tmp_path / "pnpm-workspace.yaml").write_text(
        "allowBuilds:\n  esbuild: true\n", encoding="utf-8"
    )
    k1 = prepare_cache_key(tmp_path, profile)
    k2 = prepare_cache_key(tmp_path, profile)
    assert k1 == k2
    assert len(k1) == 16


def test_prepare_cache_key_changes_when_manifest_changes(tmp_path: Path) -> None:
    profile = BuildProfile()
    (tmp_path / "package.json").write_text('{"name":"a"}', encoding="utf-8")
    k1 = prepare_cache_key(tmp_path, profile)
    (tmp_path / "package.json").write_text('{"name":"b"}', encoding="utf-8")
    k2 = prepare_cache_key(tmp_path, profile)
    assert k1 != k2


def test_write_build_profile(tmp_path: Path) -> None:
    profile = BuildProfile(builder_version="v2")
    write_build_profile(tmp_path, profile)
    raw = (tmp_path / "build-profile.json").read_text(encoding="utf-8")
    assert '"builder_version": "v2"' in raw


def test_get_builder_respects_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.builder_backend", "docker")
    assert isinstance(get_builder(), DockerBuilder)
    monkeypatch.setattr("app.core.config.settings.builder_backend", "local")
    assert isinstance(get_builder(), LocalBuilder)


@pytest.mark.asyncio
async def test_local_builder_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.name == "nt":
        # Windows 走 shell；用 echo 写文件模拟构建成功
        script = 'echo ok > dist\\index.html'
        cmd = shell_cmd(script)
    else:
        cmd = shell_cmd("mkdir -p dist && echo ok > dist/index.html")

    async def fake_communicate():
        return b"built", b""

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return await fake_communicate()

        def kill(self) -> None:
            pass

        async def wait(self) -> int:
            return 0

    async def fake_exec(*_a, **_kw):
        (tmp_path / "dist").mkdir(exist_ok=True)
        (tmp_path / "dist" / "index.html").write_text("ok", encoding="utf-8")
        return FakeProc()

    if os.name == "nt":
        monkeypatch.setattr("asyncio.create_subprocess_shell", fake_exec)
    else:
        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    result = await LocalBuilder(store_path=str(tmp_path / "store")).run(tmp_path, cmd)
    assert result.ok
    assert (tmp_path / "dist" / "index.html").is_file()


@pytest.mark.asyncio
async def test_local_builder_nonzero_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_exec(*_a, **_kw):
        class FakeProc:
            returncode = 1

            async def communicate(self):
                return b"", b"err"

            def kill(self) -> None:
                pass

            async def wait(self) -> int:
                return 0

        return FakeProc()

    if os.name == "nt":
        monkeypatch.setattr("asyncio.create_subprocess_shell", fake_exec)
    else:
        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)

    result = await LocalBuilder().run(tmp_path, shell_cmd("exit 1"))
    assert not result.ok
    assert result.error and "退出码" in result.error
