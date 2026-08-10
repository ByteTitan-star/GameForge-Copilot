"""Headless playtest for generated HTML games (B1).

MVP: static DOM checks + optional Playwright when installed (PLAYTEST_USE_PLAYWRIGHT=1).
Tests mock this module; production may enable Playwright for real JS execution.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

from app.core.cdn_policy import extract_external_refs, validate_refs


@dataclass
class PlaytestResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    console_logs: list[str] = field(default_factory=list)


class _DomScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_canvas = False
        self.has_interactive = False
        self.script_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "canvas":
            self.has_canvas = True
        if t in ("button", "input", "select", "textarea"):
            self.has_interactive = True
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if attr_map.get("onclick") or attr_map.get("onkeydown"):
            self.has_interactive = True

    def handle_data(self, data: str) -> None:
        _ = data

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)


def _extract_scripts(html: str) -> list[str]:
    return re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.I | re.S)


def _static_playtest(html: str) -> PlaytestResult:
    """Fast checks without a browser: structure + basic script sanity."""
    errors: list[str] = []
    logs: list[str] = ["playtest: static mode"]

    scanner = _DomScanner()
    try:
        scanner.feed(html)
    except Exception as e:  # noqa: BLE001 HTML parse
        errors.append(f"HTML 解析失败: {e}")
        return PlaytestResult(ok=False, errors=errors, console_logs=logs)

    if not scanner.has_canvas and not scanner.has_interactive:
        errors.append("缺少 canvas 或可交互元素（button/input/onclick）")

    scripts = _extract_scripts(html)
    for i, block in enumerate(scripts, start=1):
        src = block.strip()
        if not src:
            continue
        # 常见未闭合括号/引号
        if src.count("{") != src.count("}"):
            errors.append(f"script#{i} 花括号可能未闭合")
        if "addEventListener" in src and "keydown" not in src and "click" not in src:
            logs.append(f"script#{i}: addEventListener without keydown/click")

    # 模拟 keydown：静态模式下仅记录
    logs.append("playtest: simulated keydown ArrowRight (static, no runtime)")

    return PlaytestResult(ok=not errors, errors=errors, console_logs=logs)


async def _playwright_playtest(html_path: Path) -> PlaytestResult:
    from playwright.async_api import async_playwright

    errors: list[str] = []
    logs: list[str] = ["playtest: playwright mode"]

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        def _on_page_error(exc: Exception) -> None:
            errors.append(f"pageerror: {exc}")

        page.on("pageerror", _on_page_error)
        page.on("console", lambda msg: logs.append(f"console:{msg.type}:{msg.text}"))

        await page.goto(html_path.as_uri(), wait_until="domcontentloaded", timeout=15_000)

        has_canvas = await page.locator("canvas").count() > 0
        has_interactive = (
            await page.locator("button, input, select, textarea, [onclick]").count() > 0
        )
        if not has_canvas and not has_interactive:
            errors.append("缺少 canvas 或可交互元素")

        try:
            await page.keyboard.press("ArrowRight")
            await page.keyboard.press("Space")
            logs.append("playtest: keydown ArrowRight + Space ok")
        except Exception as e:  # noqa: BLE001 input sim
            errors.append(f"模拟按键失败: {e}")

        await browser.close()

    return PlaytestResult(ok=not errors, errors=errors, console_logs=logs)


async def run_playtest(html: str) -> PlaytestResult:
    """加载 index.html 做可玩性校验，并独立检查 CDN 白名单。

    CDN 校验与浏览器/静态检测分离：CSP 收紧后，非白名单 CDN 会被浏览器拦截，
    在此提前抓出并置顶报错，触发 QA 修复，避免产物上线后白屏。
    """
    result = await _browser_playtest(html)
    return _with_cdn_check(html, result)


async def _browser_playtest(html: str) -> PlaytestResult:
    use_pw = os.environ.get("PLAYTEST_USE_PLAYWRIGHT", "").lower() in ("1", "true", "yes")
    if use_pw:
        try:
            import playwright  # noqa: F401
        except ImportError:
            use_pw = False

    if not use_pw:
        return _static_playtest(html)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "index.html"
        path.write_text(html, encoding="utf-8")
        try:
            return await _playwright_playtest(path)
        except Exception as e:  # noqa: BLE001 playwright runtime
            fallback = _static_playtest(html)
            fallback.errors.insert(0, f"Playwright 失败，已降级静态检测: {e}")
            return fallback


def _with_cdn_check(html: str, result: PlaytestResult) -> PlaytestResult:
    """把非白名单 CDN 引用合并为 P0 错误，排在校验结果最前。"""
    ok, violations = validate_refs(extract_external_refs(html))
    if ok:
        return result
    cdn_errors = [f"引用非白名单 CDN（将被 CSP 拦截）：{v}" for v in violations]
    result.errors = cdn_errors + result.errors
    result.ok = False
    return result


def main() -> None:
    """CLI entry: python -m app.sandbox.playtest /path/to/index.html"""
    if len(sys.argv) < 2:
        print("usage: playtest <html-file>", file=sys.stderr)
        sys.exit(2)
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    result = asyncio.run(run_playtest(html))
    print("OK" if result.ok else "FAIL")
    for err in result.errors:
        print(f"ERR: {err}")
    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
