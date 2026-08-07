"""M5 沙箱本地后端：source-only / build_cmd / 失败 / 缺 index。"""

import pytest

from app.sandbox.local import LocalSandbox


@pytest.mark.asyncio
async def test_source_only_passthrough() -> None:
    r = await LocalSandbox().execute(source={"index.html": "<h1>hi</h1>"})
    assert r.ok
    assert r.files["index.html"] == b"<h1>hi</h1>"


@pytest.mark.asyncio
async def test_build_cmd_collects_output() -> None:
    r = await LocalSandbox().execute(
        source={"index.html": "<h1>hi</h1>"},
        build_cmd=["sh", "-c", "cp index.html out.html && echo built > built.txt"],
    )
    assert r.ok
    assert "out.html" in r.files and "built.txt" in r.files
    assert r.files["index.html"] == b"<h1>hi</h1>"


@pytest.mark.asyncio
async def test_build_cmd_failure() -> None:
    r = await LocalSandbox().execute(
        source={"index.html": "<h1>hi</h1>"},
        build_cmd=["sh", "-c", "exit 1"],
    )
    assert not r.ok
    assert r.error and "退出码" in r.error


@pytest.mark.asyncio
async def test_missing_index() -> None:
    r = await LocalSandbox().execute(source={"readme.txt": "no html"})
    assert not r.ok
    assert r.error == "产物缺少 index.html"
