"""结构化续写上下文（#159）：按格式定制续写轮模型可见的信息。

三层规则（确定性启发式，不调 LLM）：
- R1 全量加载：累计输出 ≤ ``llm_continuation_full_load_chars``（默认 48k，≈12k token，
  任何主流模型安全）时直接给完整原文——"代码需要完整加载"的常态路径。
- R2 结构化上下文：超限时给 头部锚点 + 符号/导入映射 + 括号栈 + 尾窗。
  解决"早期定义落在固定尾窗之外导致模型重定义/发明符号"的核心问题，
  映射用 ~4k 字符传达与全量塞入等价的绑定信息，成本差两个数量级。
- R3 文件感知（project JSON）：文件清单 + import/export 符号 + 最近写入文件。
  续写仍追加原始 JSON 字符串（保持转义与未闭合引号），但模型知道工程全貌。

配置旋钮见 config.py：尾窗默认 24000（#159 决策：原 8000 ×3），可按模型上下文
能力调整；BYOK 下游模型上下文不一，禁止一刀切拉满（长上下文检索衰减 + 成本）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.core.config import settings

FormatKind = Literal["single-html", "project-json", "text"]

# 语句起点：行首 / 分号 / 左花括号后（兼容单行压缩脚本）
_FUNC_RE = re.compile(r"(?:^|\n|[;{}>])[ \t]*(?:async[ \t]+)?function[ \t]+([A-Za-z_$][\w$]*)")
_CONST_RE = re.compile(r"(?:^|\n|[;{}>])[ \t]*(?:const|let|var)[ \t]+([A-Za-z_$][\w$]*)")
_ID_REF_RE = re.compile(r"""(?:getElementById|querySelector)\(\s*['"]#?([\w-]+)['"]""")
_ID_TAG_RE = re.compile(r"""<[^<>]+\sid=["']([^"']+)["']""")
_FILE_KEY_RE = re.compile(r"\"((?:src|public|assets)/[^\"\n]{1,80})\"\s*:")
_IMPORT_RE = re.compile(r"""import\s+(?:[\w{}\s,*$]+\s+from\s+)?['"]([^'"\n]+)['"]""")
_EXPORT_RE = re.compile(
    r"export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let)\s+([A-Za-z_$][\w$]*)"
)


def detect_format(content: str) -> FormatKind:
    text = (content or "").strip()
    lower = text[:200].lower()
    if lower.startswith("<!doctype") or lower.startswith("<html"):
        return "single-html"
    if text.startswith("{") and '"format"' in text[:400]:
        return "project-json"
    return "text"


def _unique(items: list[str], cap: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
            if len(out) >= cap:
                break
    return out


def extract_html_symbols(content: str) -> list[str]:
    """HTML：已声明函数/顶层常量/元素 id/脚本样式块计数。"""
    funcs = ", ".join(_unique(_FUNC_RE.findall(content), 40)) or "（无）"
    consts = ", ".join(_unique(_CONST_RE.findall(content), 40)) or "（无）"
    id_refs = _ID_REF_RE.findall(content) + _ID_TAG_RE.findall(content)
    ids = ", ".join(_unique(id_refs, 30)) or "（无）"
    scripts = lower_count(content, "<script")
    styles = lower_count(content, "<style")
    return [
        f"已声明函数: {funcs}",
        f"顶层常量: {consts}",
        f"元素 id: {ids}",
        f"<script> 块 {scripts} 个 / <style> 块 {styles} 个",
    ]


def lower_count(content: str, needle: str) -> int:
    return content.lower().count(needle)


def extract_project_symbols(content: str) -> list[str]:
    """project JSON：文件清单 / import 来源 / 导出符号 / 最近写入文件。"""
    files = _unique(_FILE_KEY_RE.findall(content), 30)
    lines = [
        f"文件清单: {', '.join(files) or '（尚未出现）'}",
        f"import 来源: {', '.join(_unique(_IMPORT_RE.findall(content), 30)) or '（无）'}",
        f"导出符号: {', '.join(_unique(_EXPORT_RE.findall(content), 40)) or '（无）'}",
    ]
    if files:
        lines.append(f"最近写入文件（大概率是截断处）: {files[-1]}")
    return lines


def bracket_stack_hint(content: str) -> str:
    """字符串/注释感知的括号栈扫描：报告末尾仍未闭合的结构（最多 3 个）。

    提示而非解析器：截断处若停在字符串中间，后续状态可能失真，可接受。
    """
    stack: list[tuple[str, int]] = []
    quote = ""
    in_line_comment = False
    in_block_comment = False
    line = 1
    i = 0
    text = content or ""
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if ch == "\n":
            line += 1
            in_line_comment = False
            i += 1
            continue
        if in_line_comment:
            i += 1
            continue
        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = ""
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            continue
        if ch in "{[(":
            stack.append((ch, line))
        elif ch in "}])" and stack:
            stack.pop()
        i += 1
    parts = [f"'{ch}'(约行 {ln})" for ch, ln in stack[-3:]]
    fmt = detect_format(text)
    if fmt == "single-html":
        for tag in ("script", "style"):
            opened = lower_count(text, f"<{tag}")
            closed = lower_count(text, f"</{tag}>")
            if opened > closed:
                parts.append(f"<{tag}> 未闭合 ×{opened - closed}")
    if not parts:
        return ""
    return "、".join(parts)


@dataclass
class ContinuationSections:
    """R2/R3 组装的各段内容；空段自动跳过。"""

    head: str = ""
    symbols: list[str] = field(default_factory=list)
    bracket: str = ""
    tail: str = ""
    fmt: FormatKind = "text"


def continuation_sections(content: str, *, tail_chars: int | None = None) -> ContinuationSections:
    """超限内容 → 头部锚点 + 符号映射 + 括号栈 + 尾窗。"""
    text = content or ""
    tail_limit = tail_chars if tail_chars is not None else settings.llm_continuation_tail_chars
    fmt = detect_format(text)

    head_limit = settings.llm_continuation_head_chars
    head = text[:head_limit]
    if len(text) > head_limit:
        head += "\n…（头部锚点截断）"

    symbols = extract_project_symbols(text) if fmt == "project-json" else extract_html_symbols(text)

    symbol_budget = settings.llm_continuation_symbol_map_chars
    kept: list[str] = []
    used = 0
    for line in symbols:
        if used + len(line) > symbol_budget:
            break
        kept.append(line)
        used += len(line) + 1

    return ContinuationSections(
        head=head,
        symbols=kept,
        bracket=bracket_stack_hint(text),
        tail=text[-tail_limit:] if len(text) > tail_limit else text,
        fmt=fmt,
    )
