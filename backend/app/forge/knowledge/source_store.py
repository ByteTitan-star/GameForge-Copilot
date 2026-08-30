"""Knowledge Source 本地归档（ADR-14 §3.6.2 MVP；真 S3/PG 后续）。

Pinecone 只存注入用短 `text` + `content_ptr`；原文落在本地归档根目录。
指针格式：`local://knowledge-sources/{source_id}/{document_id}/{content_hash[:16]}.md`
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings
from app.forge.knowledge.chunk_planner import content_hash_of, normalize_text

_PTR_RE = re.compile(
    r"^local://knowledge-sources/"
    r"(?P<source_id>[^/]+)/"
    r"(?P<document_id>[^/]+)/"
    r"(?P<name>[a-f0-9]{16})\.md$"
)


def knowledge_source_root() -> Path:
    return Path(settings.knowledge_source_root).expanduser().resolve()


def build_content_ptr(*, source_id: str, document_id: str, content_hash: str) -> str:
    sid = _safe_segment(source_id)
    did = _safe_segment(document_id)
    digest = (content_hash or "")[:16].lower()
    if len(digest) < 16:
        digest = content_hash_of(f"{sid}:{did}:{content_hash}")[:16]
    return f"local://knowledge-sources/{sid}/{did}/{digest}.md"


def archive_source_text(
    text: str,
    *,
    source_id: str,
    document_id: str,
) -> str:
    """写入本地归档并返回 content_ptr。"""
    cleaned = normalize_text(text)
    digest = content_hash_of(cleaned)
    ptr = build_content_ptr(
        source_id=source_id,
        document_id=document_id,
        content_hash=digest,
    )
    path = resolve_content_ptr(ptr)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(cleaned, encoding="utf-8")
    return ptr


def resolve_content_ptr(content_ptr: str) -> Path:
    """解析 local:// 指针到归档文件路径；非法指针抛 ValueError。"""
    ptr = (content_ptr or "").strip()
    match = _PTR_RE.match(ptr)
    if not match:
        raise ValueError(f"unsupported content_ptr: {ptr!r}")
    root = knowledge_source_root()
    sid = _safe_segment(match.group("source_id"))
    did = _safe_segment(match.group("document_id"))
    name = match.group("name")
    target = (root / "knowledge-sources" / sid / did / f"{name}.md").resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError("content_ptr escapes knowledge_source_root") from exc
    return target


def read_source_text(content_ptr: str) -> str:
    path = resolve_content_ptr(content_ptr)
    if not path.is_file():
        raise FileNotFoundError(content_ptr)
    return path.read_text(encoding="utf-8")


def _safe_segment(value: str) -> str:
    raw = (value or "").strip() or "unknown"
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._")
    if not cleaned or cleaned in {".", ".."} or ".." in cleaned:
        return "unknown"
    return cleaned[:120]
