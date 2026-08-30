"""产物静态文件 serving 共用逻辑（P3 多文件 Hosting）。

【安全护栏第 5 步续】artifact_csp() 按单 HTML / Vite dist 选 CSP；
实际策略在 core/cdn_policy.build_csp*。禁止直接 serve source/、build/ 前缀。
"""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi.responses import FileResponse, Response

from app.core.cdn_policy import build_csp, build_csp_project
from app.core.errors import AppError, ErrorCode
from app.hosting import store

_BLOCKED_PREFIXES = ("source/", "build/")


def is_project_artifact(game_id: uuid.UUID, version: int) -> bool:
    """dist 多文件产物：assets/ 下存在运行时资源（Vite build 输出）。"""
    assets = store.artifact_dir(game_id, version) / "assets"
    if not assets.is_dir():
        return False
    return any(p.is_file() for p in assets.iterdir())


def artifact_csp(game_id: uuid.UUID, version: int) -> str:
    if is_project_artifact(game_id, version):
        return build_csp_project()
    return build_csp()


def normalize_public_rel(path: str | None) -> str:
    """空路径或 / 视为 index.html；禁止访问 source/build 层。"""
    rel = (path or "").strip().lstrip("/")
    if not rel:
        return "index.html"
    if rel.startswith(_BLOCKED_PREFIXES) or rel.split("/", 1)[0] in ("source", "build"):
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    return rel


_SUFFIX_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".js": "application/javascript",
    ".mjs": "application/javascript",
    ".css": "text/css",
    ".html": "text/html; charset=utf-8",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


def _media_type(rel: str) -> str:
    suffix = Path(rel).suffix.lower()
    if suffix in _SUFFIX_MEDIA_TYPES:
        return _SUFFIX_MEDIA_TYPES[suffix]
    mime, _ = mimetypes.guess_type(rel)
    if mime:
        return mime
    return "application/octet-stream"


async def artifact_file_response(
    game_id: uuid.UUID,
    version: int,
    rel: str,
    *,
    headers: dict[str, str],
) -> Response:
    """按相对路径返回产物文件；本地优先 FileResponse，否则读 bytes。"""
    local = store.artifact_dir(game_id, version)
    target = (local / rel).resolve()
    base = local.resolve()
    if base not in target.parents and target != base:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    if target.is_file():
        return FileResponse(target, media_type=_media_type(rel), headers=headers)
    data = await store.read_bytes(game_id, version, rel)
    if data is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "产物不存在")
    return Response(content=data, media_type=_media_type(rel), headers=headers)
