"""确定性 HTML 结构门禁：进浏览器前拦截明显坏产物。"""

from __future__ import annotations

from app.sandbox.playtest import structural_html_errors


def test_empty_html_is_structural_error() -> None:
    assert structural_html_errors("")
    assert structural_html_errors("   ")


def test_missing_script_is_structural_error() -> None:
    html = "<!doctype html><html><body><canvas></canvas></body></html>"
    errs = structural_html_errors(html)
    assert any("script" in e.lower() for e in errs)


def test_minimal_playable_html_passes_structure() -> None:
    html = """<!doctype html><html><head><title>g</title></head>
    <body><canvas id="c"></canvas><script>console.log(1)</script></body></html>"""
    assert structural_html_errors(html) == []


def test_eval_is_flagged() -> None:
    html = "<html><body><script>eval('x')</script></body></html>"
    errs = structural_html_errors(html)
    assert any("eval" in e.lower() for e in errs)
