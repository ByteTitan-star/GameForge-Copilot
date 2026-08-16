"""Skill 正文加载（支持可选 YAML frontmatter）。"""

from __future__ import annotations

import re
from pathlib import Path

_DIR = Path(__file__).parent
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def skills_root() -> Path:
    return _DIR


def load_skill(name: str) -> str:
    """兼容旧路径：按相对 skills 根目录读取全文（去掉 frontmatter）。"""
    path = _DIR / name
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def load_skill_body(relative_path: str) -> str:
    path = _DIR / relative_path
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def _strip_frontmatter(raw: str) -> str:
    match = _FRONTMATTER.match(raw.strip())
    if not match:
        return raw
    return match.group(2)
