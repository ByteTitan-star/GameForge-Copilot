"""engine_router 单元测试：受控枚举、CDN 钉死、方法论/骨架/指南读取。"""

from app.forge.engine_router import (
    DEFAULT_ENGINE,
    SUPPORTED_ENGINES,
    engine_methodology,
    engine_routing_guide,
    engine_scaffold,
    normalize_engine_id,
    recommended_cdn_url,
)


def test_supported_engines_contract() -> None:
    assert frozenset({"canvas", "phaser3", "pixijs"}) == SUPPORTED_ENGINES
    assert DEFAULT_ENGINE == "canvas"


def test_normalize_engine_id_falls_back_for_invalid() -> None:
    assert normalize_engine_id("react") == "canvas"
    assert normalize_engine_id("") == "canvas"
    assert normalize_engine_id(None) == "canvas"
    assert normalize_engine_id("  phaser3  ") == "phaser3"


def test_recommended_cdn_url_is_pinned() -> None:
    assert (
        recommended_cdn_url("phaser3")
        == "https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js"
    )
    assert (
        recommended_cdn_url("pixijs")
        == "https://cdn.jsdelivr.net/npm/pixi.js@7.4.0/dist/pixi.min.js"
    )
    assert recommended_cdn_url("canvas") == ""
    assert recommended_cdn_url("unknown") == ""


def test_engine_methodology_returns_per_engine_text() -> None:
    assert "Phaser" in engine_methodology("phaser3")
    assert "PixiJS" in engine_methodology("pixijs")
    assert "Canvas" in engine_methodology("canvas")
    # 非法 id 回退 canvas 方法论，不抛错。
    assert engine_methodology("unity") == engine_methodology("canvas")


def test_engine_scaffold_only_for_cdn_engines() -> None:
    assert "BootScene" in engine_scaffold("phaser3")
    assert "PIXI.Application" in engine_scaffold("pixijs")
    assert engine_scaffold("canvas") == ""


def test_engine_routing_guide_nonempty() -> None:
    guide = engine_routing_guide()
    assert guide
    assert "canvas" in guide and "phaser3" in guide
