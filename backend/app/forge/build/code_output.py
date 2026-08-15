"""LLM 代码输出解析：single-html / project 结构化 JSON（§6）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from app.forge.build.routing import BuildRouting, coerce_build_routing, validate_routing

CodeFormat = Literal["single-html", "project"]


@dataclass(frozen=True)
class ParsedCodeOutput:
    format: CodeFormat
    files: dict[str, str]
    routing: BuildRouting | None = None
    errors: tuple[str, ...] = ()


def _decode_json(raw: str) -> dict[str, Any] | None:
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
    """解析 LLM 输出；非 JSON 则按 legacy single-html 处理。"""
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
