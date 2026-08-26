"""Godot P0 代码生成：template-first 物化与 LLM 输出解析（ADR-13 §3.4）。"""

from __future__ import annotations

import json
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.forge.native.godot.template_loader import materialize_godot_template

GODOT_OUTPUT_FORMAT = "godot-project"
READY_SIGNAL = "GAMEFORGE_READY"
ALLOWED_OVERLAY_PATHS = frozenset({"scenes/main.gd", "scenes/main.tscn"})
REQUIRED_OVERLAY_PATH = "scenes/main.gd"

_STORE_SKIP_PREFIXES = ("source/", "build/")
_STORE_SKIP_FILES = frozenset({"index.html", "thumb.png"})


@dataclass(frozen=True)
class ParsedGodotOutput:
    files: dict[str, str]
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


def _normalize_overlay_files(raw: object) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for rel, content in raw.items():
        if not isinstance(rel, str) or not isinstance(content, str):
            continue
        rel = rel.strip().lstrip("/").replace("\\", "/")
        if ".." in rel.split("/"):
            continue
        if rel not in ALLOWED_OVERLAY_PATHS:
            continue
        out[rel] = content
    return out


def _validate_main_gd(source: str) -> list[str]:
    errors: list[str] = []
    if READY_SIGNAL not in source:
        errors.append(f"scenes/main.gd 必须在 _ready() 中 print({READY_SIGNAL!r})")
    return errors


def parse_godot_code_output(raw: str) -> ParsedGodotOutput:
    data = _decode_json(raw)
    if data is None:
        return ParsedGodotOutput(files={}, errors=("LLM 未返回合法 godot-project JSON",))
    if data.get("format") != GODOT_OUTPUT_FORMAT:
        return ParsedGodotOutput(
            files={},
            errors=(f"format 必须是 {GODOT_OUTPUT_FORMAT!r}",),
        )
    files = _normalize_overlay_files(data.get("files"))
    errors: list[str] = []
    if REQUIRED_OVERLAY_PATH not in files:
        errors.append(f"files 必须包含 {REQUIRED_OVERLAY_PATH!r}")
    if REQUIRED_OVERLAY_PATH in files:
        errors.extend(_validate_main_gd(files[REQUIRED_OVERLAY_PATH]))
    return ParsedGodotOutput(files=files, errors=tuple(errors))


def materialize_godot_project(overlay: dict[str, str]) -> dict[str, str]:
    """物化模板并叠加 Agent 文件，返回完整工程相对路径 → 文本。"""
    with tempfile.TemporaryDirectory(prefix="gf-godot-") as tmp:
        workspace = Path(tmp) / "project"
        materialize_godot_template(workspace)
        for rel, content in overlay.items():
            if rel not in ALLOWED_OVERLAY_PATHS:
                continue
            dest = workspace / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        result: dict[str, str] = {}
        for item in workspace.rglob("*"):
            if item.is_file():
                rel = item.relative_to(workspace).as_posix()
                result[rel] = item.read_text(encoding="utf-8")
        return result


async def load_stored_godot_project(game_id: uuid.UUID, version: int) -> dict[str, str]:
    from app.hosting import store

    files: dict[str, str] = {}
    for meta in await store.list_files(game_id, version):
        path = meta.path
        if path in _STORE_SKIP_FILES:
            continue
        if any(path.startswith(prefix) for prefix in _STORE_SKIP_PREFIXES):
            continue
        if path != "project.godot" and not path.startswith("scenes/"):
            continue
        data = await store.read_bytes(game_id, version, path)
        if data is not None:
            files[path] = data.decode("utf-8", errors="replace")
    return files


def format_godot_repair_input(
    base_user_msg: str,
    *,
    overlay: dict[str, str],
    error_text: str,
    diagnosis: str,
) -> str:
    payload = {"format": GODOT_OUTPUT_FORMAT, "files": overlay}
    parts = [base_user_msg]
    if error_text:
        parts.append(f"【自动试玩/构建错误】\n{error_text[:8000]}")
    if diagnosis:
        parts.append(f"【QA 根因分析】\n{diagnosis[:4000]}")
    parts.append(
        "【当前可修改文件 JSON（仅 scenes/main.gd / scenes/main.tscn）】\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )
    return "\n\n".join(parts)
