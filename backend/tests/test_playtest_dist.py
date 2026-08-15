"""P3 dist 目录 playtest 测试。"""

from pathlib import Path

import pytest

from app.sandbox.playtest import make_playtest_result, run_playtest_dist

_CANVAS_HTML = """<!doctype html><html><body>
<canvas id="game"></canvas>
<script src="./assets/app.js"></script>
</body></html>"""


@pytest.mark.asyncio
async def test_run_playtest_dist_ok_with_mock_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text(
        "function tick(){requestAnimationFrame(tick)};tick();", encoding="utf-8"
    )

    monkeypatch.setattr(
        "app.sandbox.playtest._check_playwright_available", lambda: None
    )

    async def _ok(*_a: object, **_k: object):
        return make_playtest_result(
            errors=[], console_logs=["mock dist"], motion_signal="raf"
        )

    monkeypatch.setattr("app.sandbox.playtest._with_browser", _ok)
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


@pytest.mark.asyncio
async def test_run_playtest_dist_infra_without_playwright(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(_CANVAS_HTML, encoding="utf-8")
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setattr(
        "app.sandbox.playtest.playwright_import_available", lambda: False
    )
    result = await run_playtest_dist(dist)
    assert not result.ok
    assert result.failure_kind == "infra"
