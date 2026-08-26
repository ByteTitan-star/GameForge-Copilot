"""游戏引擎路由：受控引擎集合、CDN URL 钉死、方法论文本的单一出口。

被三方共用，单一改点：
- app.forge.prompts：build_code_prompt/build_repair_prompt 按引擎拼方法论；
- app.forge.prompts：PLAN_PROMPT 注入 routing 指南；
- app.forge.design_doc：coerce/validate 复用 SUPPORTED_ENGINES / DEFAULT_ENGINE。

CDN-UMD 路线：引擎以 `<script src>` 引用白名单 CDN 的 UMD 包，沙箱/hosting/playtest
对单文件产物零改动。版本号在此钉死，LLM 不得自行编造，避免 CDN 404。
"""

from __future__ import annotations

from pathlib import Path

from app.forge.skills import load_skill

# Web 受控引擎集合；Native 引擎（如 godot4）由 feature flag 动态并入 supported_engine_ids()。
SUPPORTED_ENGINES: frozenset[str] = frozenset({"canvas", "phaser3", "pixijs"})
DEFAULT_ENGINE = "canvas"
NATIVE_ENGINE_GODOT4 = "godot4"

_ENGINES_DIR = Path(__file__).with_name("skills") / "engines"
_TEMPLATES_DIR = Path(__file__).with_name("templates")

# 钉死经验证的 CDN UMD URL（tower_stub.html 已验证 Phaser 3.80 路径形态）。
# canvas 不需要 CDN；新增/升级引擎版本只改这一处。
_CDN_URL: dict[str, str] = {
    "phaser3": "https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js",
    "pixijs": "https://cdn.jsdelivr.net/npm/pixi.js@7.4.0/dist/pixi.min.js",
}

# 引擎最小可运行骨架文件名（templates/references/ 下）。canvas 无骨架——其方法论
# 已足够，且多数 canvas 游戏结构差异大，固定骨架反而束缚。新增引擎骨架在此登记。
_SCAFFOLD: dict[str, str] = {
    "phaser3": "scaffold-phaser3.html",
    "pixijs": "scaffold-pixijs.html",
}


def supported_engine_ids() -> frozenset[str]:
    """当前进程可用的全部引擎 id（Web + 已开启的 Native）。"""
    from app.forge.native.engine_spec import native_engine_enabled

    engines = set(SUPPORTED_ENGINES)
    if native_engine_enabled():
        engines.add(NATIVE_ENGINE_GODOT4)
    return frozenset(engines)


def is_native_engine_id(engine_id: object) -> bool:
    return isinstance(engine_id, str) and engine_id.strip() == NATIVE_ENGINE_GODOT4


def normalize_engine_id(value: object) -> str:
    """非法/缺失/未知一律回退 canvas，保证老设计稿与异常输入向后兼容。"""
    allowed = supported_engine_ids()
    if isinstance(value, str) and value.strip() in allowed:
        return value.strip()
    return DEFAULT_ENGINE


def engine_methodology(engine_id: object) -> str:
    """读取 skills/engines/{engine_id}.md；缺失时回退 canvas 方法论。"""
    if is_native_engine_id(engine_id):
        text = load_skill("engines/godot4.md")
        if text:
            return text
    eid = normalize_engine_id(engine_id)
    text = load_skill(f"engines/{eid}.md")
    if text:
        return text
    # 方法论文件缺失是配置错误，回退 canvas 仍可运行，不抛错阻断生成。
    return load_skill("engines/canvas.md") or ""


def recommended_cdn_url(engine_id: object) -> str:
    """返回钉死的引擎 CDN URL；canvas 返回空串。"""
    eid = normalize_engine_id(engine_id)
    return _CDN_URL.get(eid, "")


def engine_routing_guide() -> str:
    """注入 PLAN_PROMPT 的引擎选择指南。"""
    return load_skill("engines/routing.md")


def engine_scaffold(engine_id: object) -> str:
    """读取引擎最小可运行骨架 HTML；无骨架（canvas 或文件缺失）返回空串。

    骨架是「参考起点」而非硬模板：LLM 据此搭起 Scene/Application 结构，再按设计稿
    填玩法。缺失不阻断生成（方法论 md 已足够），仅降低一致性。
    """
    eid = normalize_engine_id(engine_id)
    filename = _SCAFFOLD.get(eid)
    if not filename:
        return ""
    path = _TEMPLATES_DIR / "references" / filename
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8").strip()


__all__ = [
    "DEFAULT_ENGINE",
    "NATIVE_ENGINE_GODOT4",
    "SUPPORTED_ENGINES",
    "engine_methodology",
    "engine_routing_guide",
    "engine_scaffold",
    "is_native_engine_id",
    "normalize_engine_id",
    "recommended_cdn_url",
    "supported_engine_ids",
]
