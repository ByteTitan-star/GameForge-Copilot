"""结构化续写上下文（#159）：R1 全量 / R2 结构化 / R3 文件感知。"""

from __future__ import annotations

from app.core.config import settings
from app.forge.continuation_context import (
    bracket_stack_hint,
    continuation_sections,
    detect_format,
    extract_html_symbols,
    extract_project_symbols,
)
from app.forge.llm_continuation import build_continuation_user_msg

_UNIQUE_EARLY_MARKER = "UNIQUE_EARLY_MARKER_x7q"  # 非符号内容，用于证明早期原文不在提示中


def _big_html(total: int = 60000) -> str:
    head = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>\n"
        "<canvas id='game'></canvas><div id='hud'></div>\n"
        "<script>\n"
    )
    # 早期定义区（~3k 处）：头部锚点之外、尾窗之外的"远距离引用"场景
    early = (
        "x" * 2500  # 越过头部锚点（2k）再放早期定义，确保只可能经符号映射可见
        + f"\nconst EARLY_CONST = 1; // {_UNIQUE_EARLY_MARKER}\n"
        + "function earlyInit(){ ctx = document.getElementById('game'); }\n"
        + "x" * 2500
    )
    filler = "x" * (total - len(head) - len(early) - 200)
    tail = "\nfunction tailFn(){ render();\n"  # 故意不闭合
    return head + early + filler + tail


def _big_project(total: int = 60000) -> str:
    head = (
        '{"format": "project", "build": "vite", "renderer": "canvas", "dependencies": [], '
        '"files": {"src/main.ts": "import { Game } from \'./engine\';\\n'
        "export function startLoop(){ Game.boot(); "
    )
    filler = "y" * (total - len(head) - 50)
    return head + filler  # 截断在 src/main.ts 的字符串值中间


def test_detect_format() -> None:
    assert detect_format("<!DOCTYPE html><html>") == "single-html"
    assert detect_format('{"format": "project"') == "project-json"
    assert detect_format("plain text") == "text"


def test_extract_html_symbols() -> None:
    html = (
        "<canvas id='game'></canvas>"
        "<script>function init(){} const speed = 1; let hud = getElementById('hud');</script>"
    )
    lines = "\n".join(extract_html_symbols(html))
    assert "init" in lines and "speed" in lines and "hud" in lines
    assert "game" in lines  # 标签 id 与 getElementById 引用都收


def test_extract_project_symbols() -> None:
    proj = (
        '{"files": {"src/main.ts": "import { Game } from \'./engine\'; '
        'export function startLoop(){}", "src/ui.ts": "export const HUD = 1;"}}'
    )
    lines = "\n".join(extract_project_symbols(proj))
    assert "src/main.ts" in lines and "src/ui.ts" in lines
    assert "./engine" in lines and "startLoop" in lines and "HUD" in lines
    assert "最近写入文件" in lines


def test_bracket_stack_ignores_strings_and_comments() -> None:
    code = "const s = '} not counted'; // { ignored\nfunction f() {\n  if (x) {\n"
    hint = bracket_stack_hint(code)
    assert "'{'(约行 2)" in hint and "'{'(约行 3)" in hint
    assert bracket_stack_hint("const a = 1; f(g[0]);") == ""


def test_r1_full_load_under_threshold() -> None:
    small = "<html><body>partial content</body>"
    msg = build_continuation_user_msg(small, context_summary="游戏：T")
    assert "【已生成内容（完整，从此处继续）】" in msg
    assert "partial content" in msg
    assert "已生成内容末尾" not in msg  # 未走尾窗路径


def test_r2_early_symbol_visible_but_raw_early_text_not() -> None:
    msg = build_continuation_user_msg(_big_html())
    # 早期定义的符号经映射对模型可见（issue 核心场景）
    assert "earlyInit" in msg and "EARLY_CONST" in msg
    # 早期非符号原文不在提示中（证明不是全量塞入）
    assert _UNIQUE_EARLY_MARKER not in msg
    # 头部锚点 + 尾窗齐备，尾部在最后（近因锚定）
    assert "【内容头部锚点】" in msg
    assert "【已生成内容末尾（从此处继续）】" in msg
    assert msg.rindex("tailFn") > msg.index("头部锚点")  # 末次出现=尾窗段，位于头部锚点之后
    assert "未闭合结构" in msg


def test_r3_project_manifest_and_raw_tail() -> None:
    msg = build_continuation_user_msg(_big_project())
    assert "文件清单" in msg and "src/main.ts" in msg
    assert "最近写入文件" in msg
    assert "startLoop" in msg and "./engine" in msg  # 跨文件绑定信息
    assert msg.rstrip().endswith("y" * 20)  # 尾部是原始（带转义）JSON 字符串


def test_tail_chars_override_and_sections() -> None:
    sections = continuation_sections(_big_html(60000), tail_chars=100)
    assert len(sections.tail) == 100
    assert sections.fmt == "single-html"


def test_config_tail_tripled() -> None:
    """#159 决策护栏：尾窗默认 24000（原 8000 ×3）。"""
    assert settings.llm_continuation_tail_chars == 24000
    assert settings.llm_continuation_full_load_chars == 48000
