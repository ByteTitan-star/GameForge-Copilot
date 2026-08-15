"""P3 dist 目录 playtest 测试。"""

from pathlib import Path

import pytest

from app.sandbox.playtest import run_playtest_dist

_CANVAS_HTML = """<!doctype html><html><body>
<canvas id="game"></canvas>
<script src="./assets/app.js"></script>
</body></html>"""


@pytest.mark.asyncio
async def test_run_playtest_dist_static_ok(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    result = await run_playtest_dist(dist)
    assert result.ok, result.errors


@pytest.mark.asyncio
async def test_run_playtest_dist_rejects_external_url(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text(
        'fetch("https://evil.example/x")', encoding="utf-8"
    )
    result = await run_playtest_dist(dist)
    assert not result.ok
    assert any("外链" in e for e in result.errors)


@pytest.mark.asyncio
async def test_run_playtest_dist_missing_asset(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    result = await run_playtest_dist(dist)
    assert not result.ok
    assert any("缺失" in e for e in result.errors)
