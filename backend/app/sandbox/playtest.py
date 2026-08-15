"""Headless playtest for generated HTML games (B1).

MVP: static DOM checks + optional Playwright when installed (PLAYTEST_USE_PLAYWRIGHT=1).
Tests mock this module; production may enable Playwright for real JS execution.
"""

from __future__ import annotations

import asyncio
import os
import re
import socket
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app.core.cdn_policy import (
    extract_external_refs,
    scan_dist_external_refs,
    validate_dist_self_contained,
    validate_refs,
)


@dataclass
class PlaytestResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    console_logs: list[str] = field(default_factory=list)
    # QA 通过分支顺带截的封面图（PNG bytes）。want_thumb=False / 静态模式 / 截图失败时均为 None。
    thumbnail: bytes | None = None


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


def _declares_engine(html: str) -> bool:
    """HTML 是否引用了受控游戏引擎 CDN（Phaser/PixiJS）。

    引擎产物的 <canvas> 由运行时注入到挂载点，源码里没有裸 <canvas>。静态模式不执行
    JS，无法证明 canvas 已挂载，因此对声明了引擎的产物跳过 canvas 存在性检查——
    这项交给运行时/Playwright/人工试玩，而非用「源码无 canvas」错判可玩性。
    """
    from app.forge.engine_router import SUPPORTED_ENGINES, recommended_cdn_url

    engine_urls = {
        url for eid in SUPPORTED_ENGINES if (url := recommended_cdn_url(eid))
    }
    return any(url in html for url in engine_urls)


def _screen_target_errors(html: str, scripts: list[str]) -> list[str]:
    """Detect the generated-game convention where state targets have no matching screen DOM."""
    source = "\n".join(scripts)
    if not re.search(r"screen-\$\{[^}]+\}", source):
        return []

    screen_ids = set(re.findall(r'id=["\']screen-([^"\']+)["\']', html, flags=re.I))
    targets = set(
        re.findall(r"\bsetScreen\(\s*[\"']([^\"']+)[\"']\s*\)", source)
    )
    missing = sorted(targets - screen_ids)
    if not missing:
        return []
    return [
        "状态切换目标缺少对应 DOM："
        + ", ".join(f"setScreen('{state}') -> #screen-{state}" for state in missing)
    ]


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

    # 引擎产物 canvas 由运行时注入，静态模式无法验证其存在；对声明了引擎的产物
    # 跳过 canvas 存在性检查，交给运行时/Playwright/人工。仍保留花括号/screen/白名单等检查。
    missing_interactive = not scanner.has_canvas and not scanner.has_interactive
    if missing_interactive and not _declares_engine(html):
        errors.append("缺少 canvas 或可交互元素（button/input/onclick）")

    scripts = _extract_scripts(html)
    errors.extend(_screen_target_errors(html, scripts))
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


async def _playwright_playtest_url(base_url: str, want_thumb: bool = False) -> PlaytestResult:
    from playwright.async_api import async_playwright

    errors: list[str] = []
    logs: list[str] = ["playtest: playwright dist mode"]
    thumbnail: bytes | None = None
    url = base_url if base_url.endswith("/") else f"{base_url}/"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page()

        def _on_page_error(exc: Exception) -> None:
            errors.append(f"pageerror: {exc}")

        page.on("pageerror", _on_page_error)

        def _on_console(msg) -> None:
            if msg.type in ("error", "warning"):
                logs.append(f"console:{msg.type}:{msg.text}")

        page.on("console", _on_console)
        await page.goto(url, wait_until="networkidle", timeout=20_000)

        has_canvas = await page.locator("canvas").count() > 0
        has_root = await page.locator("#app, #game, [data-game-root]").count() > 0
        has_interactive = (
            await page.locator("button, input, select, textarea, [onclick]").count() > 0
        )
        if not has_canvas and not has_interactive and not has_root:
            errors.append("缺少 canvas、游戏根节点或可交互元素")

        try:
            await page.keyboard.press("ArrowRight")
            await page.keyboard.press("Space")
            logs.append("playtest: keydown ArrowRight + Space ok")
        except Exception as e:  # noqa: BLE001 input sim
            errors.append(f"模拟按键失败: {e}")

        if want_thumb and not errors:
            try:
                await page.set_viewport_size({"width": 1024, "height": 576})
                await page.wait_for_timeout(500)
                thumbnail = await page.screenshot(type="png", full_page=False)
            except Exception as e:  # noqa: BLE001 playwright screenshot
                logs.append(f"thumbnail: 截图失败，已降级无封面: {e}")
                thumbnail = None

        await browser.close()

    return PlaytestResult(
        ok=not errors, errors=errors, console_logs=logs, thumbnail=thumbnail
    )


async def _playwright_playtest(html_path: Path, want_thumb: bool = False) -> PlaytestResult:
    from playwright.async_api import async_playwright

    errors: list[str] = []
    logs: list[str] = ["playtest: playwright mode"]
    thumbnail: bytes | None = None

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

        # 封面截图：仅在本次校验通过且调用方需要时截。复用已 warm 的浏览器会话，
        # 不二次冷启。16:9 视口对齐卡片比例；full_page=False 避免截到滚动区。
        # 截图是封面增强项，任何异常都降级为 None，不影响 QA 结论。
        if want_thumb and not errors:
            try:
                await page.set_viewport_size({"width": 1024, "height": 576})
                # 给 canvas/外部 CDN（tailwind/three.js）一点渲染时间；外网受限时画面可能不全，
                # 由调用方接受白屏降级。
                await page.wait_for_timeout(500)
                thumbnail = await page.screenshot(type="png", full_page=False)
            except Exception as e:  # noqa: BLE001 playwright screenshot
                logs.append(f"thumbnail: 截图失败，已降级无封面: {e}")
                thumbnail = None

        await browser.close()

    return PlaytestResult(
        ok=not errors, errors=errors, console_logs=logs, thumbnail=thumbnail
    )


def _static_playtest_dist(dist_dir: Path) -> PlaytestResult:
    index = dist_dir / "index.html"
    if not index.is_file():
        return PlaytestResult(ok=False, errors=["dist/index.html 不存在"])
    html = index.read_text(encoding="utf-8")
    errors: list[str] = []
    logs: list[str] = ["playtest: static dist mode"]
    for match in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, re.I):
        ref = match.group(1).strip()
        if ref.startswith(("http://", "https://", "data:", "blob:")):
            continue
        target = (dist_dir / ref.removeprefix("./")).resolve()
        if not target.is_file():
            errors.append(f"dist 资源缺失: {ref}")
    result = _static_playtest(html)
    result.console_logs = logs + result.console_logs
    result.errors = errors + result.errors
    result.ok = not result.errors
    return result


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def run_playtest_dist(dist_dir: Path, want_thumb: bool = False) -> PlaytestResult:
    """对 dist/ 目录启动临时静态 HTTP Server 做试玩（§17 project/vite）。"""
    refs = scan_dist_external_refs(dist_dir)
    ok, violations = validate_dist_self_contained(refs)
    if not ok:
        return PlaytestResult(
            ok=False,
            errors=[f"dist 含外链（应自包含）：{v}" for v in violations],
            console_logs=["playtest: dist external ref check failed"],
        )

    use_pw = os.environ.get("PLAYTEST_USE_PLAYWRIGHT", "").lower() in ("1", "true", "yes")
    if use_pw:
        try:
            import playwright  # noqa: F401
        except ImportError:
            use_pw = False

    if not use_pw:
        return _static_playtest_dist(dist_dir)

    port = _free_port()
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(dist_dir.resolve()), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    base_url = f"http://127.0.0.1:{port}"

    serve_thread = threading.Thread(target=server.serve_forever, daemon=True)
    serve_thread.start()
    try:
        return await _playwright_playtest_url(base_url, want_thumb=want_thumb)
    except Exception as e:  # noqa: BLE001 playwright runtime
        fallback = _static_playtest_dist(dist_dir)
        fallback.errors.insert(0, f"Playwright dist 失败，已降级静态检测: {e}")
        fallback.ok = False
        return fallback
    finally:
        server.shutdown()
        serve_thread.join(timeout=2)
        server.server_close()


async def run_playtest(html: str, want_thumb: bool = False) -> PlaytestResult:
    """加载 index.html 做可玩性校验，并独立检查 CDN 白名单。

    want_thumb=True 时，在浏览器模式下校验通过分支顺带截封面图（见 _playwright_playtest）；
    静态模式或截图失败返回 thumbnail=None。

    CDN 校验与浏览器/静态检测分离：CSP 收紧后，非白名单 CDN 会被浏览器拦截，
    在此提前抓出并置顶报错，触发 QA 修复，避免产物上线后白屏。
    """
    result = await _browser_playtest(html, want_thumb=want_thumb)
    return _with_cdn_check(html, result)


async def _browser_playtest(html: str, want_thumb: bool = False) -> PlaytestResult:
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
            return await _playwright_playtest(path, want_thumb=want_thumb)
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
