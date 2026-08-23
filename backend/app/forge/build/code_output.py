"""LLM 代码输出解析：single-html / project 结构化 JSON（§6）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from app.forge.build.routing import BuildRouting, coerce_build_routing, validate_routing

CodeFormat = Literal["single-html", "project"]


@dataclass(frozen=True)
class ParsedCodeOutput:
    """LLM 代码输出的结构化解析结果。

    场景：code/repair 节点解析 single-html 或 project JSON。
    """

    format: CodeFormat
    files: dict[str, str]
    routing: BuildRouting | None = None
    errors: tuple[str, ...] = ()


def _decode_json(raw: str) -> dict[str, Any] | None:
    """从 LLM 原始文本中提取 JSON 对象。

    场景：解析 project/single-html 结构化输出；支持 Markdown 围栏与首尾截取。
    参数：raw — LLM 返回的完整字符串。
    返回：解析成功的 dict；失败时 None。
    """
    text = raw.strip()
    if text.startswith("```"):
        first = text.find("\n")
        text = text[first + 1 :] if first >= 0 else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None


def _normalize_files(raw: object) -> dict[str, str]:
    """归一化 files 字段为安全的相对路径映射。

    场景：project JSON 入库前清洗路径，拒绝 ``..`` 与非法键。
    参数：raw — JSON 中的 files 字段。
    返回：``{相对路径: 源码文本}``；非法输入返回空 dict。
    """
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for rel, content in raw.items():
        if not isinstance(rel, str) or not rel.strip():
            continue
        if not isinstance(content, str):
            continue
        rel = rel.strip().lstrip("/").replace("\\", "/")
        if ".." in rel.split("/"):
            continue
        out[rel] = content
    return out


def parse_code_output(raw: str, *, default_engine: str = "canvas") -> ParsedCodeOutput:
    """解析 LLM 代码输出为 single-html 或 project 结构。

    场景：code/repair 节点落盘前；非 JSON 或裸 HTML 按 legacy single-html 处理。
    参数：raw — LLM 完整输出；default_engine — project 缺省 renderer。
    返回：ParsedCodeOutput（含 routing 与校验 errors）。
    """
    stripped = raw.strip()
    if stripped.lower().startswith("<!doctype") or stripped.startswith("<html"):
        return ParsedCodeOutput(format="single-html", files={"index.html": stripped})

    data = _decode_json(raw)
    if data is None:
        return ParsedCodeOutput(format="single-html", files={"index.html": stripped})

    fmt = data.get("format")
    if fmt == "project":
        routing = coerce_build_routing(data, engine_id=default_engine)
        files = _normalize_files(data.get("files"))
        errors = list(validate_routing(routing))
        if not files:
            errors.append("project 输出缺少 files")
        if not any(p.startswith("src/") for p in files):
            errors.append("project 输出至少需要一个 src/ 下源文件")
        return ParsedCodeOutput(
            format="project",
            files=files,
            routing=routing,
            errors=tuple(errors),
        )

    if fmt == "single-html":
        files = _normalize_files(data.get("files"))
        html = files.get("index.html", "")
        if not html:
            errors = ("single-html 输出缺少 files.index.html",)
            return ParsedCodeOutput(format="single-html", files={}, errors=errors)
        return ParsedCodeOutput(format="single-html", files={"index.html": html})

    # 兼容：JSON 但只有 index.html 字段
    files = _normalize_files(data.get("files"))
    if "index.html" in files:
        return ParsedCodeOutput(format="single-html", files={"index.html": files["index.html"]})

    return ParsedCodeOutput(format="single-html", files={"index.html": stripped})
