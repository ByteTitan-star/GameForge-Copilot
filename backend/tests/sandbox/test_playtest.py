"""Playtest hard-gate and B-tier motion unit tests."""

from __future__ import annotations

import pytest
from app.sandbox.motion import png_frames_differ
from app.sandbox.playtest import (
    PlaytestResult,
    make_playtest_result,
    run_playtest,
    static_playtest_diagnostic,
)


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
