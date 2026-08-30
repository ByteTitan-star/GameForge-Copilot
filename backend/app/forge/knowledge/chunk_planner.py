"""ChunkPlanner：Markdown / 长文本分块（ADR-14 §3.6.5；#146 MVP）。"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

from app.forge.knowledge.chunk_policy import (
    ChunkPolicy,
    effective_max_tokens,
    policy_by_name,
    policy_for_category,
)
from app.forge.memory.context_builder import estimate_tokens

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ChunkDraft:
    text: str
    chunk_index: int
    chunk_policy: str
    title_hint: str = ""


def normalize_text(text: str) -> str:
    """Unicode NFC + 压缩空白行。"""
    normalized = unicodedata.normalize("NFC", text or "")
    lines = [ln.rstrip() for ln in normalized.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def content_hash_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_oversized(text: str, *, max_tokens: int, overlap_tokens: int) -> list[str]:
    """按句/行滑动窗口切分，保证每段 ≤ max_tokens。"""
    if estimate_tokens(text) <= max_tokens:
        return [text]
    # 优先按句号/换行切
    parts = re.split(r"(?<=[。！？.!?\n])", text)
    parts = [p for p in parts if p and p.strip()]
    if not parts:
        # 硬切字符（CJK 约 1 token/字）
        step = max(1, max_tokens - overlap_tokens)
        return [text[i : i + max_tokens] for i in range(0, len(text), step)]

    out: list[str] = []
    buf = ""
    for part in parts:
        candidate = f"{buf}{part}" if buf else part
        if estimate_tokens(candidate) <= max_tokens:
            buf = candidate
            continue
        if buf.strip():
            out.append(buf.strip())
        # overlap: 取 buf 尾部约 overlap_tokens
        if overlap_tokens > 0 and buf:
            tail = buf
            while estimate_tokens(tail) > overlap_tokens and len(tail) > 1:
                tail = tail[len(tail) // 4 :]
            buf = f"{tail}{part}" if estimate_tokens(part) <= max_tokens else part
            if estimate_tokens(buf) > max_tokens:
                # part 本身过大：递归硬切
                out.extend(_split_oversized(part, max_tokens=max_tokens, overlap_tokens=0))
                buf = ""
        else:
            if estimate_tokens(part) > max_tokens:
                out.extend(_split_oversized(part, max_tokens=max_tokens, overlap_tokens=0))
                buf = ""
            else:
                buf = part
    if buf.strip():
        out.append(buf.strip())
    return out or [text[:max_tokens]]


def _markdown_sections(text: str) -> list[tuple[str, str]]:
    """返回 (heading_title, body) 列表；无标题则整篇一段。"""
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [("", text.strip())] if text.strip() else []
    sections: list[tuple[str, str]] = []
    # 前言（第一个标题之前）
    preface = text[: matches[0].start()].strip()
    if preface:
        sections.append(("", preface))
    for i, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        block = f"{title}\n{body}".strip() if body else title
        sections.append((title, block))
    return sections


def plan_text(
    text: str,
    *,
    policy: ChunkPolicy,
) -> list[ChunkDraft]:
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    max_tok = effective_max_tokens(policy)
    pieces = _split_oversized(
        cleaned,
        max_tokens=max_tok,
        overlap_tokens=policy.overlap_tokens,
    )
    return [
        ChunkDraft(text=p, chunk_index=i, chunk_policy=policy.name) for i, p in enumerate(pieces)
    ]


def plan_markdown(
    text: str,
    *,
    category: str,
    policy_name: str | None = None,
) -> list[ChunkDraft]:
    policy = policy_by_name(policy_name) if policy_name else None
    if policy is None:
        policy = policy_for_category(category)
    cleaned = normalize_text(text)
    if not cleaned:
        return []
    max_tok = effective_max_tokens(policy)
    drafts: list[ChunkDraft] = []
    idx = 0
    for title, section in _markdown_sections(cleaned):
        for piece in _split_oversized(
            section,
            max_tokens=max_tok,
            overlap_tokens=policy.overlap_tokens,
        ):
            drafts.append(
                ChunkDraft(
                    text=piece,
                    chunk_index=idx,
                    chunk_policy=policy.name,
                    title_hint=title,
                )
            )
            idx += 1
    return drafts


def assert_no_truncation(drafts: list[ChunkDraft], *, max_tokens: int | None = None) -> float:
    """返回 truncation_rate（超限 chunk 占比）；生产目标 0。"""
    if not drafts:
        return 0.0
    limit = max_tokens if max_tokens is not None else 480
    bad = sum(1 for d in drafts if estimate_tokens(d.text) > limit)
    return bad / len(drafts)
