"""策划稿 acceptance_criteria 的运行时探针（Playwright 会话内）。"""

from __future__ import annotations

import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal

from app.forge.design_doc import coerce_design_doc

_ENTER_STATE_RE = re.compile(
    r"(?:进入|到达|切换(?:到|为)?|返回)\s*['\"]?([a-z][a-z0-9_]*)['\"]?",
    re.I,
)
_STATE_TOKEN_RE = re.compile(
    r"\b(menu|playing|paused|level_complete|game_over|victory|start|play)\b",
    re.I,
)

_STATE_ALIASES: dict[str, frozenset[str]] = {
    "menu": frozenset({"menu", "start", "boot", "main", "title"}),
    "playing": frozenset({"playing", "play", "game", "run"}),
    "paused": frozenset({"paused", "pause"}),
    "level_complete": frozenset({"level_complete", "levelcomplete", "win", "clear"}),
    "game_over": frozenset({"game_over", "gameover", "lose", "defeat", "failed"}),
    "victory": frozenset({"victory", "win", "cleared", "all_clear"}),
}

READ_RUNTIME_STATE_JS = """() => {
  const states = new Set();
  let active = null;
  const norm = (v) => (v == null ? '' : String(v).trim().toLowerCase());
  const mark = (v) => {
    const s = norm(v);
    if (!s) return;
    states.add(s);
  };
  const setActive = (v) => {
    const s = norm(v);
    if (s) active = active || s;
    mark(s);
  };
  for (const key of ['gameState', 'currentState', 'state', '__gameState', '__AG_STATE__']) {
    const v = window[key];
    if (typeof v === 'string') setActive(v);
  }
  try {
    const game = window.Phaser?.Games?.[0];
    const scenes = game?.scene?.getScenes?.(true) || [];
    for (const scene of scenes) mark(scene?.scene?.key);
    if (scenes.length) setActive(scenes[scenes.length - 1]?.scene?.key);
  } catch (_) {}
  for (const el of document.querySelectorAll('[id^="screen-"], .screen, [data-state]')) {
    const raw = el.id?.replace(/^screen-/i, '') || el.dataset?.state || '';
    if (!raw) continue;
    mark(raw);
    const st = getComputedStyle(el);
    const visible = st.display !== 'none' && st.visibility !== 'hidden'
      && Number(st.opacity || 1) > 0;
    if (visible && st.pointerEvents !== 'none') setActive(raw);
  }
  return { active, states: Array.from(states) };
}"""

ProbeKind = Literal["after_start", "pause_resume", "terminal_state"]

_TERMINAL_CHEAT_METHODS: dict[str, tuple[str, ...]] = {
    "game_over": ("triggerGameOver", "gameOver", "lose", "triggerLose"),
    "level_complete": ("triggerLevelComplete", "levelComplete", "win", "triggerWin"),
    "victory": ("triggerVictory", "victory", "allClear", "triggerWin"),
}

INVOKE_TERMINAL_CHEAT_JS = """({ stateKey, methods }) => {
  const cheat = window.__AG_CHEAT__;
  if (!cheat || typeof cheat !== 'object') return { available: false, invoked: null };
  for (const name of methods || []) {
    const fn = cheat[name];
    if (typeof fn === 'function') {
      try { fn(); return { available: true, invoked: name }; }
      catch (e) { return { available: true, invoked: null, error: String(e) }; }
    }
  }
  if (typeof cheat.setState === 'function') {
    try { cheat.setState(stateKey); return { available: true, invoked: 'setState' }; }
    catch (e) { return { available: true, invoked: null, error: String(e) }; }
  }
  return { available: true, invoked: null };
}"""


@dataclass(frozen=True)
class RuntimeProbe:
    criterion_id: str
    target_state: str
    kind: ProbeKind
    verification: str


def extract_target_state(verification: str) -> str | None:
    text = (verification or "").strip()
    if not text:
        return None
    match = _ENTER_STATE_RE.search(text)
    if match:
        return match.group(1).lower()
    tokens = _STATE_TOKEN_RE.findall(text)
    if not tokens:
        return None
    return tokens[-1].lower()


def state_matches(observed: str | None, expected: str) -> bool:
    if not observed:
        return False
    obs = observed.strip().lower()
    exp = expected.strip().lower()
    if obs == exp:
        return True
    aliases = _STATE_ALIASES.get(exp, frozenset({exp}))
    return obs in aliases


def state_observed(observed: set[str] | list[str], expected: str) -> bool:
    return any(state_matches(item, expected) for item in observed)


def parse_runtime_probes(design_doc: dict[str, Any] | str | None) -> list[RuntimeProbe]:
    if not design_doc:
        return []
    doc = coerce_design_doc(design_doc)
    probes: list[RuntimeProbe] = []
    for criterion in doc.get("acceptance_criteria") or []:
        if not isinstance(criterion, dict):
            continue
        cid = str(criterion.get("id") or "").strip() or "AC"
        verification = str(criterion.get("verification") or "")
        lower = verification.lower()
        if "pageerror" in lower or "控制台" in verification:
            continue
        if "暂停" in verification and "继续" in verification:
            probes.append(RuntimeProbe(cid, "paused", "pause_resume", verification))
            continue
        target = extract_target_state(verification)
        if not target:
            continue
        if target in {"game_over", "level_complete", "victory"}:
            probes.append(RuntimeProbe(cid, target, "terminal_state", verification))
            continue
        if any(tok in verification for tok in ("点击", "开始", "进入 playing", "进入playing")):
            normalized = "playing" if target in {"play", "game"} else target
            probes.append(RuntimeProbe(cid, normalized, "after_start", verification))
    return probes


def terminal_source_errors(html: str, probes: list[RuntimeProbe]) -> list[str]:
    text = html or ""
    errors: list[str] = []
    for probe in probes:
        if probe.kind != "terminal_state":
            continue
        token = probe.target_state
        patterns = (
            token,
            token.replace("_", ""),
            f"screen-{token}",
            f"'{token}'",
            f'"{token}"',
        )
        if not any(p.lower() in text.lower() for p in patterns):
            errors.append(
                f"ACCEPTANCE_RT[{probe.criterion_id}]: "
                f"产物未引用状态 {token!r}（{probe.verification}）"
            )
    return errors


def source_only_probe_errors(html: str, probes: list[RuntimeProbe]) -> list[str]:
    """兼容旧名。"""
    return terminal_source_errors(html, probes)


def runtime_probe_errors(
    *,
    active_state: str | None,
    observed_states: list[str] | set[str],
    probes: list[RuntimeProbe],
) -> list[str]:
    errors: list[str] = []
    observed = set(observed_states)
    if active_state:
        observed.add(active_state)
    for probe in probes:
        if probe.kind == "after_start" and not state_observed(observed, probe.target_state):
            errors.append(
                f"ACCEPTANCE_RT[{probe.criterion_id}]: "
                f"试玩后未观察到状态 {probe.target_state!r}（{probe.verification}）"
            )
        elif probe.kind == "pause_resume" and not state_observed(observed, "paused"):
            errors.append(
                f"ACCEPTANCE_RT[{probe.criterion_id}]: "
                f"未观察到暂停态 paused（{probe.verification}）"
            )
    return errors


async def read_runtime_game_state(page: Any) -> tuple[str | None, list[str]]:
    try:
        payload = await page.evaluate(READ_RUNTIME_STATE_JS)
    except Exception:  # noqa: BLE001
        return None, []
    if not isinstance(payload, dict):
        return None, []
    active = payload.get("active")
    states = payload.get("states")
    active_state = str(active).strip().lower() if active else None
    observed = [str(s).strip().lower() for s in states if s] if isinstance(states, list) else []
    return active_state, observed


async def invoke_terminal_cheat(page: Any, target_state: str) -> dict[str, Any]:
    methods = list(_TERMINAL_CHEAT_METHODS.get(target_state, ()))
    try:
        payload = await page.evaluate(
            INVOKE_TERMINAL_CHEAT_JS,
            {"stateKey": target_state, "methods": methods},
        )
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "invoked": None, "error": str(exc)}
    return payload if isinstance(payload, dict) else {"available": False, "invoked": None}


async def terminal_cheat_probe_errors(
    page: Any,
    probes: list[RuntimeProbe],
) -> list[str]:
    errors: list[str] = []
    for probe in probes:
        if probe.kind != "terminal_state":
            continue
        result = await invoke_terminal_cheat(page, probe.target_state)
        if not result.get("available"):
            continue
        if result.get("error"):
            errors.append(
                f"ACCEPTANCE_RT[{probe.criterion_id}]: "
                f"__AG_CHEAT__ 调用失败（{probe.verification}）: {result['error']}"
            )
            continue
        if not result.get("invoked"):
            continue
        with suppress(Exception):
            await page.wait_for_timeout(120)
        active, observed = await read_runtime_game_state(page)
        if state_observed(observed, probe.target_state) or state_matches(
            active, probe.target_state
        ):
            continue
        errors.append(
            f"ACCEPTANCE_RT[{probe.criterion_id}]: "
            f"__AG_CHEAT__ 已调用 {result['invoked']!r} 但未进入 {probe.target_state!r}"
            f"（{probe.verification}）"
        )
    return errors


async def run_runtime_acceptance(
    page: Any,
    design_doc: dict[str, Any] | str | None,
    *,
    html: str = "",
) -> list[str]:
    probes = parse_runtime_probes(design_doc)
    if not probes:
        return []
    errors = terminal_source_errors(html, probes)
    active, observed = await read_runtime_game_state(page)
    errors.extend(
        runtime_probe_errors(
            active_state=active,
            observed_states=observed,
            probes=probes,
        )
    )
    errors.extend(await terminal_cheat_probe_errors(page, probes))
    return errors


async def try_pause_resume_probe(page: Any, logs: list[str]) -> None:
    """尽力触发暂停/继续，供 pause_resume 探针读取状态。"""
    for key in ("Escape", "KeyP", "p"):
        with suppress(Exception):
            await page.keyboard.press(key)
            await page.wait_for_timeout(120)
    with suppress(Exception):
        resume = page.locator("button:visible, input[type=button]:visible, [role=button]:visible")
        if await resume.count() > 0:
            await resume.first.click(timeout=800)
            logs.append("playtest: pause/resume probe click")
