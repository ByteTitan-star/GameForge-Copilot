"""策划稿驱动的确定性 HTML 验收门禁（进浏览器前）。"""

from __future__ import annotations

import re
from typing import Any

from app.forge.design_doc import coerce_design_doc
from app.forge.engine_router import normalize_engine_id
from app.sandbox.acceptance_states import required_state_source_errors

_KEY_EVENT_RE = re.compile(
    r"(keydown|keyup|keypress|KeyboardEvent|e\.code|e\.key|addEventListener\s*\(\s*['\"]key)",
    re.I,
)
_TOUCH_EVENT_RE = re.compile(
    r"(touchstart|touchend|touchmove|pointerdown|pointerup|addEventListener\s*\(\s*['\"]click)",
    re.I,
)
_SCORE_RE = re.compile(r"\bscore\b|分数|得分", re.I)
_STATE_RE = re.compile(r"\b(menu|playing|game_?over|paused|victory|level)\b|主菜单|结算", re.I)


def design_acceptance_errors(html: str, design_doc: dict[str, Any] | str | None) -> list[str]:
    """基于策划稿做轻量静态验收；空 design_doc 时跳过。"""
    if not design_doc:
        return []
    doc = coerce_design_doc(design_doc)
    text = html or ""
    lower = text.lower()
    errors: list[str] = []

    engine_id = normalize_engine_id((doc.get("engine") or {}).get("id"))
    if engine_id == "canvas" and "<canvas" not in lower:
        errors.append("ACCEPTANCE: canvas 引擎产物应包含 <canvas> 元素")
    if engine_id == "phaser3" and "phaser" not in lower:
        errors.append("ACCEPTANCE: phaser3 引擎产物应引用 Phaser")
    if engine_id == "pixijs" and "pixi" not in lower:
        errors.append("ACCEPTANCE: pixijs 引擎产物应引用 PixiJS")

    controls_text = " ".join(str(c) for c in (doc.get("controls") or [])).lower()
    needs_keyboard = any(
        tok in controls_text for tok in ("键", "wasd", "arrow", "space", "空格", "方向", "keyboard")
    )
    needs_touch = any(tok in controls_text for tok in ("触", "点击", "tap", "touch", "滑动"))
    if needs_keyboard and not _KEY_EVENT_RE.search(text):
        errors.append("ACCEPTANCE: 策划要求键盘操作，但未发现 key 事件处理")
    if needs_touch and not _TOUCH_EVENT_RE.search(text):
        errors.append("ACCEPTANCE: 策划要求触控操作，但未发现 touch/click 事件处理")

    ui_raw = doc.get("ui")
    ui: dict[str, Any] = ui_raw if isinstance(ui_raw, dict) else {}
    screens = [str(s) for s in (ui.get("screens") or [])]
    hud = [str(h) for h in (ui.get("hud") or [])]
    rules_raw = doc.get("rules")
    rules: dict[str, Any] = rules_raw if isinstance(rules_raw, dict) else {}
    if screens and not _STATE_RE.search(text):
        errors.append("ACCEPTANCE: 策划含多屏流程，但未发现 menu/playing/game_over 等状态痕迹")
    if (hud or rules.get("scoring")) and not _SCORE_RE.search(text):
        errors.append("ACCEPTANCE: 策划要求分数 HUD，但未发现 score/分数 相关变量或文案")

    errors.extend(required_state_source_errors(text, doc))
    return errors
