"""normalize_html 的 charset 兜底注入与裁剪行为。

回归：prompts 未强制 LLM 输出 ``<meta charset>``，浏览器（Windows Chrome 默认 GBK）
会把含中文的产物当 GBK 解析而乱码；normalize_html 需在缺 charset 时兜底注入 UTF-8。
"""

from app.forge.graph import normalize_html


def test_injects_charset_when_missing() -> None:
    raw = "<!DOCTYPE html><html><head><title>开始</title></head><body><h1>游戏</h1></body></html>"
    out = normalize_html(raw)
    assert '<meta charset="utf-8">' in out
    # 注入位置在 <head> 起始之后，且中文内容保留不乱码
    assert out.index('<meta charset="utf-8">') < out.index("<title>开始</title>")
    assert "游戏" in out


def test_preserves_existing_charset() -> None:
    raw = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        "<title>x</title></head><body></body></html>"
    )
    out = normalize_html(raw)
    # 已有 charset 不重复注入
    assert out.count("charset") == 1


def test_strips_markdown_fence_and_trims() -> None:
    raw = "```html\n<!DOCTYPE html><html><head></head><body><h1>标题</h1></body></html>\n```"
    out = normalize_html(raw)
    assert out.startswith("<!DOCTYPE html>")
    assert out.endswith("</html>")
    assert '<meta charset="utf-8">' in out
    assert "标题" in out
