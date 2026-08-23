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
        """校验 PlaytestResult 不变量：ok 时 errors 为空且必须有 motion_signal。

        场景：make_playtest_result 构造后自动校验。
        参数：无（dataclass 钩子）。
        返回：无；违反不变量时抛 ValueError。
        """
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
    """构造基础设施类失败结果（Playwright/Chromium 不可用等）。

    场景：_check_playwright_available、浏览器启动失败。
    参数：code - 错误码；detail - 说明；logs - 可选控制台日志。
    返回：failure_kind=infra 的 PlaytestResult。
    """
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
    """判断是否为永久性 infra 错误（重试 playtest 无意义）。

    场景：code_qa_loop 决定是否立即耗尽重试次数。
    参数：errors - 试玩错误列表。
    返回：含 PLAYWRIGHT_UNAVAILABLE / CHROMIUM_UNAVAILABLE 时为 True。
    """
    text = " ".join(str(e) for e in (errors or []))
    return any(marker in text for marker in PERMANENT_INFRA_MARKERS)


def is_browser_launch_failure(exc: BaseException) -> bool:
    """启动失败才算 infra。Browser.close 失败不得盖过已有试玩结果。"""
    msg = str(exc).lower()
    if "browser.close" in msg:
        return False
    return any(k in msg for k in ("executable", "chromium", "browser", "playwright"))


_MATTER_ADD_GROUP_RE = re.compile(r"matter\.add\.group\s*\(")


def illegal_engine_api_errors(html: str) -> list[str]:
    """已知会立刻 pageerror 的引擎 API 幻觉；产品错误，不必再开浏览器。"""
    if not _MATTER_ADD_GROUP_RE.search(html):
        return []
    return [
        "PAGE_ERROR: this.matter.add.group is not a function"
        "（Phaser Matter 无 group API；显示分组用 this.add.group()；"
        "物理体用 matter.add.rectangle/circle/image + constraint）"
    ]


def playwright_import_available() -> bool:
    """检测 playwright 包是否已安装。

    场景：_check_playwright_available 前置探测。
    参数：无。
    返回：可 import playwright 时为 True。
    """
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def _check_playwright_available() -> PlaytestResult | None:
    """同步探测 Playwright + Chromium 是否可用。

    场景：run_playtest / run_playtest_dist 开浏览器前。
    参数：无。
    返回：不可用时返回 infra PlaytestResult，否则 None。
    """
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
    """静态 HTML 扫描器：检测 canvas 与可交互元素。

    场景：static_playtest_diagnostic。
    参数：无（继承 HTMLParser）。
    返回：通过 has_canvas / has_interactive 属性暴露结果。
    """

    def __init__(self) -> None:
        """初始化扫描状态（has_canvas / has_interactive 均为 False）。"""
        super().__init__()
        self.has_canvas = False
        self.has_interactive = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """记录 canvas、表单控件与 onclick/onkeydown 等可交互标记。

        场景：feed HTML 时逐标签回调。
        参数：tag - 标签名；attrs - 属性列表。
        返回：无（更新实例状态）。
        """
        t = tag.lower()
        if t == "canvas":
            self.has_canvas = True
        if t in ("button", "input", "select", "textarea"):
            self.has_interactive = True
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if attr_map.get("onclick") or attr_map.get("onkeydown"):
            self.has_interactive = True

    def handle_data(self, data: str) -> None:
        """HTMLParser 文本节点回调（本扫描器不处理文本）。

        场景：feed 时占位以满足 Parser 接口。
        参数：data - 文本内容。
        返回：无。
        """
        _ = data

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """自闭合标签回调，复用 handle_starttag 逻辑。

        场景：如 <input /> 等标签。
        参数：tag、attrs。
        返回：无。
        """
        self.handle_starttag(tag, attrs)


def _extract_scripts(html: str) -> list[str]:
    """从 HTML 提取内联 <script> 块正文。

    场景：static_playtest_diagnostic、_screen_target_errors。
    参数：html - 完整 HTML 字符串。
    返回：各 script 块内容列表。
    """
    return re.findall(r"<script[^>]*>(.*?)</script>", html, flags=re.I | re.S)


def _declares_engine(html: str) -> bool:
    """判断 HTML 是否引用受支持的游戏引擎 CDN。

    场景：静态诊断时豁免「无 canvas 但有引擎脚本」。
    参数：html - 页面 HTML。
    返回：含推荐引擎 CDN URL 时为 True。
    """
    from app.forge.engine_router import SUPPORTED_ENGINES, recommended_cdn_url

    engine_urls = {url for eid in SUPPORTED_ENGINES if (url := recommended_cdn_url(eid))}
    return any(url in html for url in engine_urls)


def _screen_target_errors(html: str, scripts: list[str]) -> list[str]:
    """检测 setScreen 目标与 #screen-* DOM id 是否一致。

    场景：static_playtest_diagnostic。
    参数：html、内联 scripts 列表。
    返回：缺失 screen DOM 的错误文案列表。
    """
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
    """多个全屏 screen 同时接收 pointer-events 时生成产品错误文案。

    场景：_fail_if_stacked_screens。
    参数：ids - 可见全屏层 id 列表。
    返回：错误字符串或 None（少于 2 层）。
    """
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
    """在页面执行 JS 检测叠层 screen，有则追加 OVERLAY 错误。

    场景：_inject_inputs 点击按钮前。
    参数：page - Playwright Page；errors - 可变错误列表。
    返回：无。
    """
    try:
        ids = await page.evaluate(_STACKED_SCREEN_JS)
    except Exception:  # noqa: BLE001
        return
    msg = classify_stacked_screens(ids if isinstance(ids, list) else [])
    if msg:
        errors.append(msg)


async def _click_unobstructed_buttons(page: Any, logs: list[str], errors: list[str]) -> None:
    """尝试点击第一个可见可用按钮，验证基础交互。

    场景：_inject_inputs。
    参数：page、logs、errors。
    返回：无；失败时写入 errors。
    """
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
    """试玩输入注入：叠层检查 → 按钮点击 → 键盘按键。

    场景：_session_playtest 加载页面后。
    参数：page、logs、errors。
    返回：无。
    """
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
) -> PlaytestResult:
    """单页 Playwright 会话：加载、注入输入、检测运动信号、可选截图。

    场景：_with_browser 内核心试玩逻辑。
    参数：page、url、want_thumb、mode_label、goto_timeout_ms。
    返回：PlaytestResult（含 motion_signal 或产品/infra 错误）。
    """
    errors: list[str] = []
    logs: list[str] = [f"playtest: {mode_label}"]

    def _on_page_error(exc: Exception) -> None:
        """Playwright pageerror 回调：记录页面 JS 异常。

        场景：_session_playtest 监听运行时错误。
        参数：exc — 页面抛出的异常。
        返回：无。
        """
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
    """关闭浏览器，失败仅打 warning 不抛异常。

    场景：_with_browser finally 清理。
    参数：browser - Playwright Browser。
    返回：无。
    """
    try:
        await browser.close()
    except Exception as exc:  # noqa: BLE001
        log.warning("playtest browser.close failed", extra={"error": str(exc)})


async def _with_browser(
    url: str, want_thumb: bool, mode_label: str, timeout: int
) -> PlaytestResult:
    """启动 headless Chromium 并执行 _session_playtest。

    场景：run_playtest / run_playtest_dist。
    参数：url、want_thumb、mode_label、页面 goto 超时毫秒。
    返回：PlaytestResult。
    """
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
    """校验 dist/index.html 引用的本地资源文件是否存在。

    场景：run_playtest_dist 构建产物检查。
    参数：dist_dir - Vite 输出目录。
    返回：缺失资源错误列表。
    """
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
    """绑定 127.0.0.1:0 获取系统分配的临时端口。

    场景：_serve 本地静态文件服务。
    参数：无。
    返回：可用端口号。
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _serve(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread, str]:
    """在后台线程启动 ThreadingHTTPServer 托管目录。

    场景：run_playtest / run_playtest_dist 临时 HTTP 服务。
    参数：directory - 静态根目录。
    返回：(server, thread, base_url)。
    """
    port = _free_port()
    handler = lambda *args, **kwargs: SimpleHTTPRequestHandler(  # noqa: E731
        *args, directory=str(directory.resolve()), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{port}"


def _stop_server(server: ThreadingHTTPServer, thread: threading.Thread) -> None:
    """优雅关闭临时 HTTP 服务与守护线程。

    场景：run_playtest finally 块。
    参数：server、thread。
    返回：无。
    """
    server.shutdown()
    thread.join(timeout=2)
    server.server_close()


async def run_playtest_dist(dist_dir: Path, want_thumb: bool = False) -> PlaytestResult:
    """对 Vite dist 目录做自包含检查 + Playwright 冒烟试玩。

    场景：Code QA 构建产物门禁（生产路径）。
    参数：dist_dir、want_thumb - 是否截缩略图。
    返回：PlaytestResult。
    """
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

    unavailable = await asyncio.to_thread(_check_playwright_available)
    if unavailable is not None:
        return unavailable

    server, thread, base = _serve(dist_dir)
    try:
        return await _with_browser(f"{base}/", want_thumb, "playwright dist mode", 20_000)
    finally:
        _stop_server(server, thread)


async def run_playtest(html: str, want_thumb: bool = False) -> PlaytestResult:
    """对单文件 HTML 做引擎 API 预检 + Playwright 冒烟试玩。

    场景：Forge code_qa_loop、CLI main。
    参数：html - 完整页面；want_thumb。
    返回：附带 CDN 白名单校验的 PlaytestResult。
    """
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

    unavailable = await asyncio.to_thread(_check_playwright_available)
    if unavailable is not None:
        return _with_cdn_check(html, unavailable)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = root / "index.html"
        path.write_text(html, encoding="utf-8")
        server, thread, base = _serve(root)
        try:
            result = await _with_browser(
                f"{base}/index.html", want_thumb, "playwright mode", 15_000
            )
        finally:
            _stop_server(server, thread)
    return _with_cdn_check(html, result)


def _with_cdn_check(html: str, result: PlaytestResult) -> PlaytestResult:
    """合并 CDN 白名单违规与既有试玩结果。

    场景：run_playtest 返回前。
    参数：html、已有 PlaytestResult。
    返回：可能追加 CSP 相关错误的 PlaytestResult。
    """
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
    """CLI 入口：对指定 HTML 文件运行 run_playtest 并打印结果。

    场景：``python -m app.sandbox.playtest <file>``。
    参数：sys.argv[1] 为 HTML 路径。
    返回：无；进程 exit 0/1/2。
    """
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
