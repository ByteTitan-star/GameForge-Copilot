"""Playtest hard-gate and B-tier motion unit tests."""

from __future__ import annotations

import pytest

from app.sandbox.motion import png_frames_differ
from app.sandbox.playtest import (
    PlaytestResult,
    _click_unobstructed_buttons,
    _with_browser,
    classify_click_failures,
    classify_stacked_screens,
    is_browser_launch_failure,
    make_playtest_result,
    run_playtest,
    static_playtest_diagnostic,
)


def test_classify_overlay_click_failures() -> None:
    intercept = "Timeout 1200ms exceeded. <button id='btn-resume'> intercepts pointer events"
    msg = classify_click_failures([intercept, intercept], attempted=2)
    assert msg is not None
    assert msg.startswith("OVERLAY_BLOCKS_POINTER")


def test_classify_generic_click_failure() -> None:
    msg = classify_click_failures(["button not found"], attempted=1)
    assert msg is not None
    assert msg.startswith("INPUT_INJECTION_FAILED")


def test_classify_stacked_screens() -> None:
    msg = classify_stacked_screens(["screen-start", "screen-paused"])
    assert msg is not None
    assert msg.startswith("OVERLAY_BLOCKS_POINTER")
    assert classify_stacked_screens(["screen-start"]) is None


class _FakeBtn:
    def __init__(self, *, click_error: str | None = None) -> None:
        self.click_error = click_error
        self.clicked = False

    async def is_enabled(self) -> bool:
        return True

    async def click(self, timeout: int = 0) -> None:
        if self.click_error:
            raise RuntimeError(self.click_error)
        self.clicked = True


class _FakeLocator:
    def __init__(self, buttons: list[_FakeBtn]) -> None:
        self._buttons = buttons

    async def count(self) -> int:
        return len(self._buttons)

    def nth(self, index: int) -> _FakeBtn:
        return self._buttons[index]


class _FakePage:
    def __init__(self, buttons: list[_FakeBtn]) -> None:
        self._locator = _FakeLocator(buttons)

    def locator(self, _selector: str) -> _FakeLocator:
        return self._locator


@pytest.mark.asyncio
async def test_click_fails_when_start_intercepted_even_if_resume_works() -> None:
    start = _FakeBtn(click_error="Timeout 1200ms exceeded. intercepts pointer events")
    resume = _FakeBtn()
    logs: list[str] = []
    errors: list[str] = []
    await _click_unobstructed_buttons(_FakePage([start, resume]), logs, errors)
    assert any(e.startswith("OVERLAY_BLOCKS_POINTER") for e in errors)
    assert not resume.clicked


def test_playtest_result_rejects_ok_with_errors() -> None:
    with pytest.raises(ValueError):
        PlaytestResult(ok=True, errors=["x"], console_logs=[], motion_signal="raf")


def test_playtest_result_rejects_ok_without_motion() -> None:
    with pytest.raises(ValueError):
        PlaytestResult(ok=True, errors=[], console_logs=[])


def test_make_playtest_result_ok_requires_motion() -> None:
    r = make_playtest_result(errors=[], motion_signal="raf")
    assert r.ok
    assert r.failure_kind is None
    assert r.motion_signal == "raf"


def test_make_playtest_result_errors_force_not_ok() -> None:
    r = make_playtest_result(errors=["boom"], motion_signal="raf")
    assert not r.ok
    assert r.motion_signal is None
    assert r.failure_kind == "product"


def test_png_frames_differ() -> None:
    assert not png_frames_differ(b"abc", b"abc")
    assert png_frames_differ(b"a" * 200, b"b" * 200)


def test_static_diagnostic_never_ok() -> None:
    html = """
    <html><body>
    <canvas id="game"></canvas>
    <script>document.addEventListener('keydown', function(e) {});</script>
    </body></html>
    """
    r = static_playtest_diagnostic(html)
    assert not r.ok
    assert r.failure_kind == "product"


def test_static_diagnostic_flags_missing_interactive() -> None:
    r = static_playtest_diagnostic("<html><body><h1>hello</h1></body></html>")
    assert not r.ok
    assert any("canvas" in e or "交互" in e for e in r.errors)


def test_static_diagnostic_unbalanced_braces() -> None:
    html = """
    <html><body><canvas></canvas>
    <script>function f() { console.log(1); </script>
    </body></html>
    """
    r = static_playtest_diagnostic(html)
    assert not r.ok
    assert any("花括号" in e for e in r.errors)


def test_cdn_whitelist_accepts_engine_scripts() -> None:
    from app.core.cdn_policy import extract_external_refs, validate_refs

    html = (
        '<script src="https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"></script>'
        '<script src="https://cdn.jsdelivr.net/npm/pixi.js@7.4.0/dist/pixi.min.js"></script>'
    )
    ok, violations = validate_refs(extract_external_refs(html))
    assert ok, violations


@pytest.mark.asyncio
async def test_run_playtest_without_playwright_is_infra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.sandbox.playtest.playwright_import_available", lambda: False)
    r = await run_playtest("<html><body><canvas></canvas></body></html>")
    assert not r.ok
    assert r.failure_kind == "infra"
    assert any("PLAYWRIGHT_UNAVAILABLE" in e for e in r.errors)


def test_browser_close_error_is_not_launch_failure() -> None:
    exc = RuntimeError("Browser.close: Connection closed while reading from the driver")
    assert not is_browser_launch_failure(exc)


def test_missing_chromium_is_launch_failure() -> None:
    exc = RuntimeError("Executable doesn't exist at .../chromium")
    assert is_browser_launch_failure(exc)


def test_static_diagnostic_flags_matter_add_group() -> None:
    html = """
    <html><body><canvas id="game"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"></script>
    <script>this.matter.add.group();</script>
    </body></html>
    """
    r = static_playtest_diagnostic(html)
    assert not r.ok
    assert r.failure_kind == "product"
    assert any("matter.add.group" in e for e in r.errors)


@pytest.mark.asyncio
async def test_run_playtest_flags_matter_add_group_as_product(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.sandbox.playtest.playwright_import_available", lambda: False)
    html = "<html><body><canvas></canvas><script>this.matter.add.group()</script></body></html>"
    r = await run_playtest(html)
    assert r.failure_kind == "product"
    assert any("matter.add.group" in e for e in r.errors)


_PAGE_ERROR_X = "PAGE_ERROR: Cannot read properties of undefined (reading 'x')"
_CLOSE_ERR = "Browser.close: Connection closed while reading from the driver"


class _FakeBrowser:
    def __init__(self, close_error: str | None = None) -> None:
        self.close_error = close_error

    async def new_page(self) -> object:
        return object()

    async def close(self) -> None:
        if self.close_error:
            raise RuntimeError(self.close_error)


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser

    async def launch(self, headless: bool = True) -> _FakeBrowser:
        _ = headless
        return self._browser


class _FakePlaywright:
    def __init__(self, browser: _FakeBrowser, *, aexit_error: str | None = None) -> None:
        self.chromium = _FakeChromium(browser)
        self.aexit_error = aexit_error

    async def __aenter__(self) -> _FakePlaywright:
        return self

    async def __aexit__(self, *_a: object) -> bool:
        if self.aexit_error:
            raise RuntimeError(self.aexit_error)
        return False


def _install_fake_playwright(monkeypatch: pytest.MonkeyPatch, fake: _FakePlaywright) -> None:
    import sys
    import types

    fake_api = types.ModuleType("playwright.async_api")
    fake_api.async_playwright = lambda: fake
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_api)


def _product_session_result() -> PlaytestResult:
    return make_playtest_result(
        errors=[_PAGE_ERROR_X],
        console_logs=["playtest: playwright mode"],
        failure_kind="product",
    )


def _patch_session(monkeypatch: pytest.MonkeyPatch, result: PlaytestResult) -> None:
    from app.sandbox import playtest as playtest_mod

    async def _fake_session(*_a: object, **_k: object) -> PlaytestResult:
        return result

    monkeypatch.setattr(playtest_mod, "_session_playtest", _fake_session)


@pytest.mark.asyncio
async def test_with_browser_keeps_session_result_when_close_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_result = _product_session_result()
    _install_fake_playwright(monkeypatch, _FakePlaywright(_FakeBrowser(close_error=_CLOSE_ERR)))
    _patch_session(monkeypatch, session_result)
    result = await _with_browser("http://127.0.0.1/index.html", False, "playwright mode", 1000)
    assert result.failure_kind == "product"
    assert result.errors == session_result.errors
    assert not any("BROWSER_LAUNCH_FAILED" in e for e in result.errors)


@pytest.mark.asyncio
async def test_with_browser_keeps_session_result_when_playwright_aexit_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_result = _product_session_result()
    _install_fake_playwright(
        monkeypatch,
        _FakePlaywright(_FakeBrowser(), aexit_error=_CLOSE_ERR),
    )
    _patch_session(monkeypatch, session_result)
    result = await _with_browser("http://127.0.0.1/index.html", False, "playwright mode", 1000)
    assert result.failure_kind == "product"
    assert result.errors == session_result.errors
    assert not any("BROWSER_LAUNCH_FAILED" in e for e in result.errors)


@pytest.mark.asyncio
async def test_run_playtest_mock_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_check() -> None:
        return None

    async def _fake_browser(*_a: object, **_k: object) -> PlaytestResult:
        return make_playtest_result(
            errors=[],
            console_logs=["mock"],
            motion_signal="raf",
            thumbnail=b"\x89PNG",
        )

    monkeypatch.setattr("app.sandbox.playtest._check_playwright_available", lambda: None)
    monkeypatch.setattr("app.sandbox.playtest._with_browser", _fake_browser)
    html = "<html><body><canvas id='game'></canvas></body></html>"
    r = await run_playtest(html, want_thumb=True)
    assert r.ok
    assert r.motion_signal == "raf"
    assert r.thumbnail == b"\x89PNG"
