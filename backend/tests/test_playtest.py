"""B1: sandbox playtest unit tests."""

import pytest

from app.sandbox.playtest import run_playtest


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
