"""P4 Capability Precheck：RequiredCapabilities × CapabilityProfile，禁止关键词黑名单。"""

from __future__ import annotations

from typing import Any

PROFILE_VERSION = "2026-08-18.1"

RUNTIME_PROFILE: dict[str, Any] = {
    "profile_version": PROFILE_VERSION,
    "renderers": ["dom", "canvas2d", "phaser2d", "pixijs"],
    "webgl_3d": False,
    "physics_2d": True,
    "realtime_multiplayer": False,
    "backend_server": False,
    "limits": {
        "max_build_seconds": 120,
        "max_bundle_mb": 30,
        "max_asset_count": 80,
    },
}

_ENGINE_RENDERER = {
    "canvas": "canvas2d",
    "phaser3": "phaser2d",
    "pixijs": "pixijs",
}

_BOOL_KEYS = ("physics_2d", "realtime_multiplayer", "backend_server", "webgl_3d")


def _as_bool(value: Any, default: bool = False) -> bool:
    """将 JSON/配置中的布尔字段规范为 bool。

    场景：coerce_required_capabilities。
    参数：value - 原始值；default - 无法解析时的默认。
    返回：布尔结果。
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no", ""}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def coerce_required_capabilities(raw: Any, *, engine_id: str = "canvas") -> dict[str, Any]:
    """从 design_doc 片段归一化 required_capabilities 结构。

    场景：capability_conflicts / developability_precheck。
    参数：raw - 原始 dict；engine_id - 默认 renderer 映射。
    返回：含 renderer 与 physics_2d 等字段的 dict。
    """
    src = raw if isinstance(raw, dict) else {}
    renderer = str(src.get("renderer") or "").strip() or _ENGINE_RENDERER.get(engine_id, "canvas2d")
    caps: dict[str, Any] = {"renderer": renderer}
    for key in _BOOL_KEYS:
        caps[key] = _as_bool(src.get(key), False)
    return caps


def capability_conflicts(
    design_doc: dict[str, Any],
    *,
    profile: dict[str, Any] | None = None,
) -> list[str]:
    """只比较结构化 required_capabilities，不扫描玩法文案。"""
    runtime = profile or RUNTIME_PROFILE
    caps = coerce_required_capabilities(
        design_doc.get("required_capabilities"),
        engine_id=str((design_doc.get("engine") or {}).get("id") or "canvas"),
    )
    conflicts: list[str] = []
    allowed = list(runtime.get("renderers") or [])
    if caps["renderer"] not in allowed:
        conflicts.append(
            f"required_capabilities.renderer={caps['renderer']!r} "
            f"不在 CapabilityProfile.renderers={allowed}"
        )
    for key in _BOOL_KEYS:
        if caps[key] and not bool(runtime.get(key)):
            conflicts.append(
                f"required_capabilities.{key}=true 不被 CapabilityProfile 支持"
                f"（profile.{key}=false）"
            )
    return conflicts


def developability_precheck(design_doc: dict[str, Any]) -> list[str]:
    """Plan Confirm 前的可实现性预检；空列表表示可通过。"""
    return capability_conflicts(design_doc)
