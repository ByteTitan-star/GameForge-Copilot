"""B1: sandbox playtest unit tests."""

import pytest

from app.sandbox.playtest import run_playtest


def _chromium_available() -> bool:
    """探测 playwright + chromium 是否可用（封面截图的前提）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    try:
        with sync_playwright() as pw:
            pw.chromium.launch(headless=True).close()
        return True
    except Exception:  # noqa: BLE001 未装 chromium / 缺系统依赖均视为不可用
        return False


_NEED_CHROMIUM = pytest.mark.skipif(
    not _chromium_available(), reason="封面截图需 playwright + chromium（worker 可选依赖）"
)


@pytest.mark.asyncio
async def test_playtest_passes_with_canvas_and_script() -> None:
    html = """
    <html><body>
    <canvas id="game"></canvas>
    <script>
    document.addEventListener('keydown', function(e) {});
    </script>
    </body></html>
    """
    r = await run_playtest(html)
    assert r.ok, r.errors
    assert r.console_logs


@pytest.mark.asyncio
async def test_playtest_fails_without_interactive() -> None:
    html = "<html><body><h1>hello</h1></body></html>"
    r = await run_playtest(html)
    assert not r.ok
    assert any("canvas" in e or "交互" in e for e in r.errors)


@pytest.mark.asyncio
async def test_playtest_fails_unbalanced_braces() -> None:
    html = """
    <html><body><canvas></canvas>
    <script>function f() { console.log(1); </script>
    </body></html>
    """
    r = await run_playtest(html)
    assert not r.ok
    assert any("花括号" in e for e in r.errors)


@pytest.mark.asyncio
async def test_playtest_fails_when_screen_state_has_no_matching_dom() -> None:
    html = """
    <html><body>
    <div id="screen-menu"><button>开始</button></div>
    <div id="screen-game"></div>
    <script>
    function setScreen(next) {
      document.getElementById(`screen-${next}`);
    }
    setScreen('playing');
    </script>
    </body></html>
    """
    r = await run_playtest(html)
    assert not r.ok
    assert any("#screen-playing" in e for e in r.errors)


@pytest.mark.asyncio
async def test_playtest_accepts_matching_screen_state_dom() -> None:
    html = """
    <html><body>
    <div id="screen-menu"><button>开始</button></div>
    <div id="screen-playing"></div>
    <script>
    function setScreen(next) {
      document.getElementById(`screen-${next}`);
    }
    setScreen('playing');
    </script>
    </body></html>
    """
    r = await run_playtest(html)
    assert r.ok, r.errors


def test_cdn_whitelist_accepts_engine_scripts() -> None:
    """Phaser/PixiJS 走 jsdelivr/unpkg CDN，已在白名单内，validate_refs 不得误杀。"""
    from app.core.cdn_policy import extract_external_refs, validate_refs

    html = (
        '<script src="https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/pixi.js@7.4.0/dist/pixi.min.js"></script>'
    )
    ok, violations = validate_refs(extract_external_refs(html))
    assert ok, violations


@pytest.mark.asyncio
async def test_playtest_passes_with_engine_cdn_and_canvas() -> None:
    """含 Phaser CDN 脚本 + canvas 的产物应通过试玩（CDN 在白名单）。"""
    html = """
    <html><body>
    <canvas id="game"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"></script>
    <script>document.addEventListener('keydown', function(e) {});</script>
    </body></html>
    """
    r = await run_playtest(html)
    assert r.ok, r.errors


@pytest.mark.asyncio
async def test_playtest_accepts_engine_mounted_canvas() -> None:
    """引擎产物 canvas 由运行时注入挂载点，源码无裸 <canvas>；静态模式不得误判。

    静态模式不执行 JS，无法验证引擎是否真的挂上了 canvas；此项交给运行时/Playwright/
    人工，而非用「源码无 canvas」错判可玩性。
    """
    html = """
    <html><body>
    <div id="game"></div>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"></script>
    <script>document.addEventListener('keydown', function(e) {});</script>
    </body></html>
    """
    r = await run_playtest(html)
    assert r.ok, r.errors


@pytest.mark.asyncio
async def test_playtest_still_rejects_bare_page_without_engine() -> None:
    """无 canvas 且无引擎声明的纯静态页仍应被拒（引擎兼容不得放宽通用保护）。"""
    html = "<html><body><h1>no game</h1></body></html>"
    r = await run_playtest(html)
    assert not r.ok
    assert any("canvas" in e or "交互" in e for e in r.errors)


@pytest.mark.asyncio
async def test_static_mode_never_returns_thumbnail(monkeypatch: pytest.MonkeyPatch) -> None:
    """默认无 PLAYTEST_USE_PLAYWRIGHT → 静态模式，want_thumb 也无法截图，thumbnail 恒 None。

    静态模式没有浏览器会话，截图能力只在 playwright 模式下具备（见 integration 标记的用例）。
    """
    monkeypatch.delenv("PLAYTEST_USE_PLAYWRIGHT", raising=False)
    html = (
        "<html><body><canvas id='game'></canvas>"
        "<script>document.addEventListener('keydown',e=>{})</script></body></html>"
    )
    r = await run_playtest(html, want_thumb=True)
    assert r.ok
    assert r.thumbnail is None


@pytest.mark.asyncio
@_NEED_CHROMIUM
async def test_playwright_mode_returns_thumbnail_on_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实 chromium 模式：通过 HTML + want_thumb=True 应返回非空 PNG。

    需 worker 装好 chromium 且 PLAYTEST_USE_PLAYWRIGHT=1；无 chromium 环境自动跳过。
    """
    monkeypatch.setenv("PLAYTEST_USE_PLAYWRIGHT", "1")
    html = """
    <html><body>
    <canvas id="game" width="100" height="100"></canvas>
    <script>document.addEventListener('keydown', function(e) {});</script>
    </body></html>
    """
    r = await run_playtest(html, want_thumb=True)
    assert r.ok, r.errors
    assert r.thumbnail is not None
    assert r.thumbnail.startswith(b"\x89PNG")


@pytest.mark.asyncio
@_NEED_CHROMIUM
async def test_playwright_mode_no_thumbnail_when_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实 chromium 模式：QA 不通过（缺交互元素）时不截图，thumbnail=None 且 ok=False。"""
    monkeypatch.setenv("PLAYTEST_USE_PLAYWRIGHT", "1")
    html = "<html><body><h1>no game here</h1></body></html>"
    r = await run_playtest(html, want_thumb=True)
    assert not r.ok
    assert r.thumbnail is None
