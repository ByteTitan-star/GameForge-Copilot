"""Headless playtest：生产路径强制 Playwright 可交互冒烟（B 档硬门禁）。

静态 DOM 检查仅作诊断 helper（`static_playtest_diagnostic`），不得作为生产 QA 通过路径。
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Literal

from app.core.cdn_policy import (
    extract_external_refs,
    scan_dist_external_refs,
    validate_dist_self_contained,
    validate_refs,
)
from app.core.config import settings
from app.sandbox.acceptance_gate import design_acceptance_errors
from app.sandbox.acceptance_runtime import (
    parse_runtime_probes,
    run_runtime_acceptance,
    try_pause_resume_probe,
)
from app.sandbox.motion import RAF_INIT_SCRIPT, evaluate_motion_signal

log = logging.getLogger(__name__)

FailureKind = Literal["product", "build", "infra"]
MotionSignal = Literal["raf", "canvas_diff", "engine_runtime"]


@dataclass
class PlaytestResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    console_logs: list[str] = field(default_factory=list)
    thumbnail: bytes | None = None
    failure_kind: FailureKind | None = None
    motion_signal: MotionSignal | None = None

    def __post_init__(self) -> None:
        if self.ok and self.errors:
            raise ValueError("PlaytestResult invariant: ok=True requires errors==[]")
        if self.ok and self.failure_kind is not None:
            raise ValueError("PlaytestResult invariant: ok=True requires failure_kind=None")
        if self.ok and self.motion_signal is None:
            raise ValueError("PlaytestResult invariant: ok=True requires motion_signal")


def make_playtest_result(
    *,
    errors: list[str] | None = None,
    console_logs: list[str] | None = None,
    thumbnail: bytes | None = None,
    failure_kind: FailureKind | None = None,
    motion_signal: MotionSignal | None = None,
) -> PlaytestResult:
    """统一派生 ok，避免多分支手改 result.ok 破坏不变量。"""
    errs = list(errors or [])
    logs = list(console_logs or [])
    ok = (not errs) and failure_kind is None and motion_signal is not None
    return PlaytestResult(
        ok=ok,
        errors=errs,
        console_logs=logs,
        thumbnail=thumbnail if ok else None,
        failure_kind=None if ok else (failure_kind or ("product" if errs else "product")),
        motion_signal=motion_signal if ok else None,
    )


def _infra_result(code: str, detail: str, logs: list[str] | None = None) -> PlaytestResult:
    return make_playtest_result(
        errors=[f"{code}: {detail}"],
        console_logs=logs or ["playtest: infra failure"],
        failure_kind="infra",
    )


# 环境类 infra：重试 playtest 不会变好，应立即耗尽并走 sandbox_failed / 可恢复暂停
PERMANENT_INFRA_MARKERS = (
    "PLAYWRIGHT_UNAVAILABLE",
    "CHROMIUM_UNAVAILABLE",
)


def is_permanent_infra_error(errors: list[str] | None) -> bool:
    text = " ".join(str(e) for e in (errors or []))
    return any(marker in text for marker in PERMANENT_INFRA_MARKERS)


def is_browser_launch_failure(exc: BaseException) -> bool:
    """启动失败才算 infra。Browser.close 失败不得盖过已有试玩结果。"""
    msg = str(exc).lower()
    if "browser.close" in msg:
        return False
    return any(k in msg for k in ("executable", "chromium", "browser", "playwright"))


_MATTER_ADD_GROUP_RE = re.compile(r"matter\.add\.group\s*\(")
_EVAL_RE = re.compile(r"\beval\s*\(")
_SCRIPT_RE = re.compile(r"<script\b", re.I)
_SCRIPT_CLOSE_RE = re.compile(r"</script\s*>", re.I)


def illegal_engine_api_errors(html: str) -> list[str]:
    """已知会立刻 pageerror 的引擎 API 幻觉；产品错误，不必再开浏览器。"""
    if not _MATTER_ADD_GROUP_RE.search(html):
        return []
    return [
        "PAGE_ERROR: this.matter.add.group is not a function"
        "（Phaser Matter 无 group API；显示分组用 this.add.group()；"
        "物理体用 matter.add.rectangle/circle/image + constraint）"
    ]


def structural_html_errors(html: str) -> list[str]:
    """进浏览器前的确定性结构门禁：空页、无脚本、危险 API。"""
    text = (html or "").strip()
    errors: list[str] = []
    if not text:
        errors.append("STRUCTURAL: 产物 HTML 为空")
        return errors
    if not _SCRIPT_RE.search(text):
        errors.append("STRUCTURAL: 缺少 <script>，无法运行游戏逻辑")
    opens = len(_SCRIPT_RE.findall(text))
    closes = len(_SCRIPT_CLOSE_RE.findall(text))
    if opens and closes and opens != closes:
        errors.append("STRUCTURAL: <script> 标签未正确闭合")
    if _EVAL_RE.search(text):
        errors.append("STRUCTURAL: 禁止使用 eval()")
    return errors


def playwright_import_available() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def _check_playwright_available() -> PlaytestResult | None:
    if not playwright_import_available():
        return _infra_result(
            "PLAYWRIGHT_UNAVAILABLE",
            "playwright package is not installed "
            "(worker: uv sync --extra playwright && uv run playwright install chromium). "
            "Not related to Docker/Daytona sandbox.",
        )
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return _infra_result(
            "CHROMIUM_UNAVAILABLE",
            f"chromium launch failed: {exc}. Fix: uv run playwright install chromium",
        )
    return None


class _DomScanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.has_canvas = False
        self.has_interactive = False

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
    from app.forge.engine_router import SUPPORTED_ENGINES, recommended_cdn_url

    engine_urls = {url for eid in SUPPORTED_ENGINES if (url := recommended_cdn_url(eid))}
    return any(url in html for url in engine_urls)


def _screen_target_errors(html: str, scripts: list[str]) -> list[str]:
    source = "\n".join(scripts)
    if not re.search(r"screen-\$\{[^}]+\}", source):
        return []
    screen_ids = set(re.findall(r'id=["\']screen-([^"\']+)["\']', html, flags=re.I))
    targets = set(re.findall(r"\bsetScreen\(\s*[\"']([^\"']+)[\"']\s*\)", source))
    missing = sorted(targets - screen_ids)
    if not missing:
        return []
    return [
        "状态切换目标缺少对应 DOM："
        + ", ".join(f"setScreen('{state}') -> #screen-{state}" for state in missing)
    ]


def static_playtest_diagnostic(html: str) -> PlaytestResult:
    """诊断用静态检查。永不作为生产 QA 通过（成功结构检查仍 ok=False）。"""
    errors: list[str] = []
    logs: list[str] = ["playtest: static diagnostic (not a QA pass path)"]
    scanner = _DomScanner()
    try:
        scanner.feed(html)
    except Exception as e:  # noqa: BLE001
        errors.append(f"HTML 解析失败: {e}")
        return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    missing_interactive = not scanner.has_canvas and not scanner.has_interactive
    if missing_interactive and not _declares_engine(html):
        errors.append("缺少 canvas 或可交互元素（button/input/onclick）")
    scripts = _extract_scripts(html)
    errors.extend(_screen_target_errors(html, scripts))
    errors.extend(illegal_engine_api_errors(html))
    for i, block in enumerate(scripts, start=1):
        src = block.strip()
        if not src:
            continue
        if src.count("{") != src.count("}"):
            errors.append(f"script#{i} 花括号可能未闭合")
    if not errors:
        errors.append("STATIC_DIAGNOSTIC_ONLY: structural checks passed (not runtime QA)")
    return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")


_static_playtest = static_playtest_diagnostic

OVERLAY_POINTER_MARK = "intercepts pointer events"

_BTN_SELECTOR = "button:visible, input[type=button]:visible, [role=button]:visible"

_STACKED_SCREEN_JS = """() => {
  const els = Array.from(document.querySelectorAll('.screen, [id^="screen-"]'));
  const ids = [];
  for (const el of els) {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden') continue;
    if ((s.pointerEvents || '') === 'none') continue;
    const r = el.getBoundingClientRect();
    if (r.width >= window.innerWidth * 0.8 && r.height >= window.innerHeight * 0.8) {
      ids.push(el.id || el.tagName.toLowerCase());
    }
  }
  return ids;
}"""


def classify_stacked_screens(ids: list[str] | None) -> str | None:
    names = [str(item) for item in (ids or []) if item]
    if len(names) < 2:
        return None
    return (
        "OVERLAY_BLOCKS_POINTER: multiple fullscreen screens receive pointer-events "
        f"({', '.join(names)}). Only one screen may be interactive."
    )


def classify_click_failures(click_errors: list[str], attempted: int) -> str | None:
    """把「全部被遮罩拦住」收成明确的产品失败，避免误当成瞬时 timeout。"""
    if attempted <= 0 or not click_errors:
        return None
    if any(OVERLAY_POINTER_MARK in err for err in click_errors):
        return (
            "OVERLAY_BLOCKS_POINTER: visible buttons are covered by another screen "
            "(e.g. #screen-paused). Only one screen may receive pointer-events."
        )
    return f"INPUT_INJECTION_FAILED: click: {click_errors[-1]}"


async def _fail_if_stacked_screens(page: Any, errors: list[str]) -> None:
    try:
        ids = await page.evaluate(_STACKED_SCREEN_JS)
    except Exception:  # noqa: BLE001
        return
    msg = classify_stacked_screens(ids if isinstance(ids, list) else [])
    if msg:
        errors.append(msg)


async def _click_unobstructed_buttons(page: Any, logs: list[str], errors: list[str]) -> None:
    btn = page.locator(_BTN_SELECTOR)
    try:
        count = await btn.count()
    except Exception as e:  # noqa: BLE001
        errors.append(f"INPUT_INJECTION_FAILED: click: {e}")
        return
    if count <= 0:
        return
    for i in range(count):
        target = btn.nth(i)
        try:
            if not await target.is_enabled():
                continue
            await target.click(timeout=1_200)
            logs.append("playtest: button click ok")
            return
        except Exception as e:  # noqa: BLE001
            classified = classify_click_failures([str(e)], attempted=1)
            errors.append(classified or f"INPUT_INJECTION_FAILED: click: {e}")
            return


async def _inject_inputs(page: Any, logs: list[str], errors: list[str]) -> None:
    # 先查叠层，再点按钮。暂停层盖住 START 时，Resume 可点也不能当 qa_ok。
    await _fail_if_stacked_screens(page, errors)
    if errors:
        return
    await _click_unobstructed_buttons(page, logs, errors)
    if errors:
        return
    try:
        await page.keyboard.press("ArrowRight")
        await page.keyboard.press("Space")
        logs.append("playtest: keydown ArrowRight + Space ok")
    except Exception as e:  # noqa: BLE001
        errors.append(f"INPUT_INJECTION_FAILED: {e}")


async def _session_playtest(
    page: Any,
    *,
    url: str,
    want_thumb: bool,
    mode_label: str,
    goto_timeout_ms: int,
    design_doc: dict[str, Any] | None = None,
    runtime_design_doc: dict[str, Any] | None = None,
    html: str = "",
) -> PlaytestResult:
    errors: list[str] = []
    logs: list[str] = [f"playtest: {mode_label}"]

    def _on_page_error(exc: Exception) -> None:
        errors.append(f"PAGE_ERROR: {exc}")

    page.on("pageerror", _on_page_error)
    page.on(
        "console",
        lambda msg: (
            logs.append(f"console:{msg.type}:{msg.text}")
            if msg.type in ("error", "warning", "log")
            else None
        ),
    )
    await page.add_init_script(RAF_INIT_SCRIPT)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=goto_timeout_ms)
        await page.wait_for_timeout(300)
    except Exception as e:  # noqa: BLE001
        return make_playtest_result(
            errors=[f"PAGE_LOAD_FAILED: {e}"],
            console_logs=logs,
            failure_kind="product",
        )

    if errors:
        return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    await _inject_inputs(page, logs, errors)
    await page.wait_for_timeout(200)
    if errors:
        return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    if (
        runtime_design_doc
        and settings.forge_acceptance_runtime
        and any(p.kind == "pause_resume" for p in parse_runtime_probes(runtime_design_doc))
    ):
        await try_pause_resume_probe(page, logs)
        await page.wait_for_timeout(150)

    if runtime_design_doc and settings.forge_acceptance_runtime:
        rt_errors = await run_runtime_acceptance(page, runtime_design_doc, html=html)
        if rt_errors:
            errors.extend(rt_errors)
            return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    motion = await evaluate_motion_signal(page)
    if motion is None:
        errors.append("NO_RUNTIME_SIGNAL: no raf/canvas_diff/engine_runtime")
        return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    if errors:
        return make_playtest_result(errors=errors, console_logs=logs, failure_kind="product")

    thumbnail: bytes | None = None
    if want_thumb:
        try:
            await page.set_viewport_size({"width": 1024, "height": 576})
            await page.wait_for_timeout(300)
            thumbnail = await page.screenshot(type="png", full_page=False)
        except Exception as e:  # noqa: BLE001
            logs.append(f"thumbnail: 截图失败，已降级无封面: {e}")
            thumbnail = None

    return make_playtest_result(
        errors=[],
        console_logs=logs,
        thumbnail=thumbnail,
        motion_signal=motion,  # type: ignore[arg-type]
    )


async def _close_browser_quietly(browser: Any) -> None:
    try:
        await browser.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("playtest browser.close failed", extra={"error": str(exc)})


async def _with_browser(
    url: str,
    want_thumb: bool,
    mode_label: str,
    timeout: int,
    *,
    design_doc: dict[str, Any] | None = None,
    runtime_design_doc: dict[str, Any] | None = None,
    html: str = "",
) -> PlaytestResult:
    from playwright.async_api import async_playwright

    session_result: PlaytestResult | None = None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                session_result = await _session_playtest(
                    page,
                    url=url,
                    want_thumb=want_thumb,
                    mode_label=mode_label,
                    goto_timeout_ms=timeout,
                    design_doc=design_doc,
                    runtime_design_doc=runtime_design_doc,
                    html=html,
                )
                return session_result
            finally:
                await _close_browser_quietly(browser)
    except Exception as e:  # noqa: BLE001
        if session_result is not None:
            log.warning("playtest cleanup failed", extra={"error": str(e)})
            return session_result
        if is_browser_launch_failure(e):
            return _infra_result("BROWSER_LAUNCH_FAILED", str(e))
        return make_playtest_result(
            errors=[f"PAGE_LOAD_FAILED: {e}"],
            console_logs=[f"playtest: {mode_label}"],
            failure_kind="product",
        )


def _dist_asset_errors(dist_dir: Path) -> list[str]:
    index = dist_dir / "index.html"
    if not index.is_file():
        return ["dist/index.html 不存在"]
    html = index.read_text(encoding="utf-8")
    errors: list[str] = []
    for match in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)["']""", html, re.I):
        ref = match.group(1).strip()
        if ref.startswith(("http://", "https://", "data:", "blob:", "#")):
            continue
        target = (dist_dir / ref.removeprefix("./")).resolve()
        if not target.is_file():
            errors.append(f"dist 资源缺失: {ref}")
    return errors


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _serve(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    port = _free_port()
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(directory.resolve()), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


def _stop_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    server.shutdown()
    thread.join(timeout=2)
    server.server_close()


def _design_acceptance_result(
    html: str, design_doc: dict[str, Any] | None
) -> PlaytestResult | None:
    if not design_doc:
        return None
    errors = design_acceptance_errors(html, design_doc)
    if not errors:
        return None
    return make_playtest_result(
        errors=errors,
        console_logs=["playtest: design acceptance gate"],
        failure_kind="product",
    )


async def run_playtest_dist(
    dist_dir: Path,
    want_thumb: bool = False,
    *,
    design_doc: dict[str, Any] | None = None,
    runtime_design_doc: dict[str, Any] | None = None,
) -> PlaytestResult:
    refs = scan_dist_external_refs(dist_dir)
    ok, violations = validate_dist_self_contained(refs)
    if not ok:
        return make_playtest_result(
            errors=[f"dist 含外链（应自包含）：{v}" for v in violations],
            console_logs=["playtest: dist external ref check failed"],
            failure_kind="product",
        )

    asset_errors = _dist_asset_errors(dist_dir)
    if asset_errors:
        return make_playtest_result(
            errors=asset_errors,
            console_logs=["playtest: dist asset check"],
            failure_kind="product",
        )

    index_html = dist_dir / "index.html"
    dist_html = index_html.read_text(encoding="utf-8") if index_html.is_file() else ""
    if design_doc and dist_html:
        acceptance = _design_acceptance_result(dist_html, design_doc)
        if acceptance is not None:
            return acceptance

    unavailable = await asyncio.to_thread(_check_playwright_available)
    if unavailable is not None:
        return unavailable

    server, thread, base = _serve(dist_dir)
    try:
        return await _with_browser(
            f"{base}/",
            want_thumb,
            "playwright dist mode",
            20_000,
            design_doc=design_doc,
            runtime_design_doc=runtime_design_doc,
            html=dist_html,
        )
    finally:
        _stop_server(server, thread)


async def run_playtest(
    html: str,
    want_thumb: bool = False,
    *,
    design_doc: dict[str, Any] | None = None,
    runtime_design_doc: dict[str, Any] | None = None,
) -> PlaytestResult:
    api_errors = illegal_engine_api_errors(html)
    if api_errors:
        return _with_cdn_check(
            html,
            make_playtest_result(
                errors=api_errors,
                console_logs=["playtest: engine api lint"],
                failure_kind="product",
            ),
        )

    acceptance = _design_acceptance_result(html, design_doc)
    if acceptance is not None:
        return _with_cdn_check(html, acceptance)

    unavailable = await asyncio.to_thread(_check_playwright_available)
    if unavailable is not None:
        return _with_cdn_check(html, unavailable)

    structural = structural_html_errors(html)
    if structural:
        return _with_cdn_check(
            html,
            make_playtest_result(
                errors=structural,
                console_logs=["playtest: structural gate"],
                failure_kind="product",
            ),
        )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "index.html"
        path.write_text(html, encoding="utf-8")
        server, thread, base = _serve(root)
        try:
            result = await _with_browser(
                f"{base}/index.html",
                want_thumb,
                "playwright mode",
                15_000,
                design_doc=design_doc,
                runtime_design_doc=runtime_design_doc,
                html=html,
            )
        finally:
            _stop_server(server, thread)
    return _with_cdn_check(html, result)


def _with_cdn_check(html: str, result: PlaytestResult) -> PlaytestResult:
    ok, violations = validate_refs(extract_external_refs(html))
    if ok:
        return result
    cdn_errors = [f"引用非白名单 CDN（将被 CSP 拦截）：{v}" for v in violations]
    return make_playtest_result(
        errors=cdn_errors + result.errors,
        console_logs=result.console_logs,
        failure_kind=result.failure_kind or "product",
    )


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: playtest <html-file>", file=sys.stderr)
        sys.exit(2)
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    result = asyncio.run(run_playtest(html))
    print("OK" if result.ok else "FAIL")
    for err in result.errors:
        print(f"ERR: {err}")
    if result.failure_kind:
        print(f"KIND: {result.failure_kind}")
    sys.exit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
