"""策划稿驱动的确定性验收门禁。"""

from __future__ import annotations

import pytest

from app.forge.design_doc import coerce_design_doc
from app.sandbox.acceptance_gate import design_acceptance_errors


def _doc() -> dict:
    return coerce_design_doc(
        {
            "title": "测试",
            "gameplay": "收集方块得分",
            "controls": ["方向键移动", "空格跳跃", "触屏点击跳跃"],
            "engine": {"id": "canvas"},
            "ui": {"screens": ["主菜单", "游戏", "结算"], "hud": ["分数"]},
            "rules": {"scoring": ["吃到食物加分"]},
        },
        "测试",
    )


def test_missing_canvas_for_canvas_engine() -> None:
    html = "<html><body><script>function tick(){}</script></body></html>"
    errs = design_acceptance_errors(html, _doc())
    assert any("canvas" in e.lower() for e in errs)


def test_missing_keyboard_handler() -> None:
    html = """<html><body><canvas></canvas>
    <script>canvas.addEventListener('touchstart',()=>{});</script></body></html>"""
    errs = design_acceptance_errors(html, _doc())
    assert any("键盘" in e or "keydown" in e.lower() for e in errs)


def test_minimal_passing_html() -> None:
    html = """<!doctype html><html><body><canvas id="c"></canvas>
    <script>
    let score=0;
    let state='menu';
    document.addEventListener('keydown', e=>{ if(e.code==='Space'){} });
    canvas.addEventListener('touchstart', ()=>{});
  </script></body></html>"""
    assert design_acceptance_errors(html, _doc()) == []


@pytest.mark.asyncio
async def test_run_playtest_runs_acceptance_gate() -> None:
    from app.sandbox.playtest import run_playtest

    html = "<html><body><script>console.log(1)</script></body></html>"
    result = await run_playtest(html, design_doc=_doc())
    assert not result.ok
    assert any("ACCEPTANCE" in e for e in result.errors)
