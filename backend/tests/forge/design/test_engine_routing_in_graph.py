"""引擎路由在提示词层的回归测试。

验证按 design_doc.engine.id 拼出的 system prompt 含对应引擎方法论与钉死 CDN URL，
且修复分支强制保持引擎不变。纯函数级，不驱动整图（整图由 test_forge_reliability 覆盖）。
"""

from app.forge.engine_router import recommended_cdn_url
from app.forge.prompts import (
    CODE_PROMPT,
    build_code_prompt,
    build_repair_prompt,
)


def test_build_code_prompt_phaser3_has_methodology_and_cdn() -> None:
    prompt = build_code_prompt("phaser3")
    # 引擎方法论注入（Phaser Scene/生命周期）
    assert "Phaser" in prompt
    assert "Scene" in prompt
    # 钉死 CDN URL 原样出现，禁止 LLM 自行编版本
    assert recommended_cdn_url("phaser3") in prompt


def test_build_code_prompt_pixijs_has_methodology_and_cdn() -> None:
    prompt = build_code_prompt("pixijs")
    assert "PixiJS" in prompt
    assert "Ticker" in prompt
    assert recommended_cdn_url("pixijs") in prompt


def test_build_code_prompt_canvas_has_no_cdn_clause() -> None:
    prompt = build_code_prompt("canvas")
    # canvas 无 CDN，不应出现引擎脚本 URL
    assert "cdn.jsdelivr.net/npm/phaser" not in prompt
    assert "cdn.jsdelivr.net/npm/pixi" not in prompt
    # 仍含通用硬约束骨架
    assert "HTML5" in prompt
    assert "requestAnimationFrame" in prompt


def test_build_code_prompt_invalid_engine_falls_back_to_canvas() -> None:
    prompt = build_code_prompt("unity")
    assert "cdn.jsdelivr.net/npm/phaser" not in prompt
    assert "Canvas" in prompt  # 回退 canvas 方法论


def test_default_code_prompt_is_canvas() -> None:
    """向后兼容别名 CODE_PROMPT 等价于 build_code_prompt(canvas)。"""
    assert "cdn.jsdelivr.net/npm/phaser" not in CODE_PROMPT
    assert build_code_prompt("canvas") == CODE_PROMPT


def test_repair_prompt_keeps_engine_choice() -> None:
    """修复分支必须含「保持原 engine 选型不变」，防止修复时切换引擎造成回归。"""
    prompt = build_repair_prompt("phaser3")
    assert "保持原 engine 选型不变" in prompt
    assert recommended_cdn_url("phaser3") in prompt
