"""Skill 正文加载（支持可选 YAML frontmatter）。"""

from __future__ import annotations

import re
from pathlib import Path

_DIR = Path(__file__).parent
_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def skills_root() -> Path:
    """返回 skills 包根目录 Path。

    场景：路径解析、测试。
    参数：无。
    返回：backend/app/forge/skills 目录。
    """
    return _DIR


def load_skill(name: str) -> str:
    """兼容旧路径：按相对 skills 根目录读取全文（去掉 frontmatter）。"""
    path = _DIR / name
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def load_skill_body(relative_path: str) -> str:
    """按相对路径加载 Skill 正文（去掉 YAML frontmatter）。

    场景：router._load、skill_bundle_hash。
    参数：relative_path - 如 conventions.md。
    返回：正文文本，缺失文件返回空串。
    """
    path = _DIR / relative_path
    if not path.exists():
        return ""
    return _strip_frontmatter(path.read_text(encoding="utf-8")).strip()


def _strip_frontmatter(raw: str) -> str:
    """去掉 SKILL.md 顶部 YAML frontmatter，保留正文。

    场景：load_skill / load_skill_body。
    参数：raw - 文件全文。
    返回：正文部分。
    """
    match = _FRONTMATTER.match(raw.strip())
    if not match:
        return raw
    return match.group(2)
