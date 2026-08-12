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


@pytest.mark.asyncio
async def test_chinese_html_roundtrips_as_utf8() -> None:
    # 回归：sandbox 写盘必须显式 UTF-8。Windows 默认 CP936(GBK) 会让含中文的 HTML 以
    # GBK 字节落盘，随后 qa_node 的 read_text(encoding="utf-8") 直接 UnicodeDecodeError。
    # LocalSandbox/DockerSandbox 共享同一写入反模式，docker 后端同源修复（CI 无容器不测）。
    html = "<!DOCTYPE html><html><body><h1>开始游戏</h1></body></html>"
    r = await LocalSandbox().execute(source={"index.html": html})
    assert r.ok
    assert r.files["index.html"].decode("utf-8") == html
