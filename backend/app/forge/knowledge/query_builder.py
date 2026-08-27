"""RetrievalQueryBuilder（ADR-14 §3.7；不 embed 完整 transcript）。"""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.config import settings
from app.forge.knowledge.guards import clip_query_text
from app.forge.knowledge.policy import policy_for_node
from app.forge.knowledge.types import RetrievalQuery

_TAG_RE = re.compile(r"【[^】]*】")
_WS_RE = re.compile(r"\s+")


def _strip_fences(text: str) -> str:
    cleaned = _TAG_RE.sub(" ", text)
    cleaned = cleaned.replace("MEMORY_DATA", " ")
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned[:1200]


def _design_doc_hints(design_doc: dict[str, Any] | None) -> str:
    if not design_doc:
        return ""
    parts: list[str] = []
    for key in ("title", "genre", "summary", "core_loop", "target_platform"):
        val = design_doc.get(key)
        if isinstance(val, str) and val.strip():
            parts.append(val.strip())
    gameplay = design_doc.get("gameplay")
    if isinstance(gameplay, dict):
        for key in ("mechanics", "objective", "controls"):
            val = gameplay.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val.strip())
    if not parts:
        try:
            return json.dumps(design_doc, ensure_ascii=False, sort_keys=True)[:600]
        except (TypeError, ValueError):
            return ""
    return " ".join(parts)[:600]


def build_retrieval_query(
    *,
    node: str,
    current_input: str,
    design_doc: dict[str, Any] | None = None,
) -> RetrievalQuery | None:
    policy = policy_for_node(node)
    if policy is None:
        return None
    req = _strip_fences(current_input)
    hints = _design_doc_hints(design_doc)
    query_text = " ".join(p for p in (req, hints) if p).strip()
    if not query_text:
        return None
    max_tokens = max(0, int(settings.knowledge_query_max_tokens))
    query_text = clip_query_text(query_text, max_tokens=max_tokens)
    if not query_text:
        return None
    return RetrievalQuery(
        query_text=query_text,
        domains=policy.domains,
        categories=policy.categories,
    )
