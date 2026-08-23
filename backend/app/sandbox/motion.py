"""B 档运行弱信号：rAF / canvas 帧差 / 已知引擎 runtime。

QA 不得用自有 requestAnimationFrame 观察循环制造自证信号；
仅统计页面业务代码触发的 rAF callback。
"""

from __future__ import annotations

from typing import Any, Protocol

# 在业务脚本之前注入：统计页面自己请求并执行的 rAF 次数。
RAF_INIT_SCRIPT = """
(() => {
  if (window.__gfRafHooked) return;
  window.__gfRafHooked = true;
  window.__gfRafCount = 0;
  const orig = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = (cb) =>
    orig((t) => {
      window.__gfRafCount = (window.__gfRafCount || 0) + 1;
      return cb(t);
    });
})();
"""

_RAF_MIN_DELTA = 2
_CANVAS_DIFF_SAMPLE_STEP = 17
_CANVAS_DIFF_MIN_HITS = 8


class _PageLike(Protocol):
    async def evaluate(self, expression: str) -> Any:
        """在页面上下文执行 JavaScript 表达式。"""

    async def wait_for_timeout(self, timeout: float) -> None:
        """等待指定毫秒（Playwright page.wait_for_timeout）。"""

    def locator(self, selector: str) -> Any:
        """按 CSS 选择器定位元素。"""


def png_frames_differ(a: bytes, b: bytes) -> bool:
    """两帧 PNG 是否有可观测差异（稀疏采样，避免抗锯齿噪声误杀）。"""
    if a == b:
        return False
    if abs(len(a) - len(b)) >= 64:
        return True
    n = min(len(a), len(b))
    hits = 0
    for i in range(0, n, _CANVAS_DIFF_SAMPLE_STEP):
        if a[i] != b[i]:
            hits += 1
            if hits >= _CANVAS_DIFF_MIN_HITS:
                return True
    return False


async def probe_raf_activity(page: _PageLike, *, window_ms: int = 400) -> bool:
    """检测窗口期内页面业务代码触发的 rAF 回调是否足够活跃。

    场景：B 档 motion 弱信号探测。
    参数：page - Playwright Page；window_ms - 观测窗口毫秒数。
    返回：增量 ≥ _RAF_MIN_DELTA 时为 True。
    """
    before = int(await page.evaluate("() => window.__gfRafCount || 0") or 0)
    await page.wait_for_timeout(window_ms)
    after = int(await page.evaluate("() => window.__gfRafCount || 0") or 0)
    return after - before >= _RAF_MIN_DELTA


async def probe_canvas_frame_diff(page: _PageLike, *, window_ms: int = 400) -> bool:
    """对首个可见 canvas 间隔截图并比较帧差。

    场景：无 rAF 但有 canvas 动画的游戏。
    参数：page、window_ms。
    返回：两帧 PNG 有可观测差异时为 True。
    """
    canvases = page.locator("canvas")
    if await canvases.count() <= 0:
        return False
    canvas = canvases.first
    try:
        if not await canvas.is_visible():
            return False
        shot_a = await canvas.screenshot(type="png")
        await page.wait_for_timeout(window_ms)
        shot_b = await canvas.screenshot(type="png")
    except Exception:  # noqa: BLE001 截图失败不算 motion
        return False
    return png_frames_differ(shot_a, shot_b)


async def probe_engine_runtime(page: _PageLike) -> bool:
    """已知引擎已真实挂载；空 #game/#app 根节点不算。"""
    return bool(
        await page.evaluate(
            """() => {
  const hasPhaser =
    typeof Phaser !== 'undefined' &&
    Array.isArray(Phaser.GAMES) &&
    Phaser.GAMES.length > 0;
  if (hasPhaser) return true;
  if (typeof PIXI !== 'undefined') {
    const c = document.querySelector('canvas');
    if (c && c.width > 0 && c.height > 0) return true;
  }
  const mounted = document.querySelector(
    '#game canvas, #app canvas, [data-game-root] canvas'
  );
  return !!(mounted && mounted.width > 0 && mounted.height > 0);
}"""
        )
    )


async def evaluate_motion_signal(page: _PageLike) -> str | None:
    """返回 raf | canvas_diff | engine_runtime；全无则 None。"""
    if await probe_raf_activity(page):
        return "raf"
    if await probe_canvas_frame_diff(page):
        return "canvas_diff"
    if await probe_engine_runtime(page):
        return "engine_runtime"
    return None
