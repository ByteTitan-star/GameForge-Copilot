"""P2 Skill catalog：metadata 可发现，正文按需加载。"""

from __future__ import annotations

import hashlib
from functools import lru_cache

from app.forge.skills.loader import load_skill_body
from app.forge.skills.models import SkillMeta

# 约 8 个 Methodology + 2 个 Policy；引擎正文复用 engines/*.md，不重复拷贝。
_REGISTRY: tuple[SkillMeta, ...] = (
    SkillMeta(
        id="policy/conventions",
        name="Engineering Conventions",
        kind="policy",
        nodes=("code", "repair", "plan", "art"),
        description="Platform engineering/output contract; not optional.",
        path="conventions.md",
    ),
    SkillMeta(
        id="policy/playtest",
        name="Playtest Policy",
        kind="policy",
        nodes=("code", "repair", "qa"),
        description="B-tier Playwright gate; static checks cannot synthesize qa_ok.",
        path="playtest.md",
    ),
    SkillMeta(
        id="art/pixel-art",
        name="Pixel Art",
        kind="methodology",
        nodes=("art", "art_options", "art_detail"),
        description="Pixel-art visual direction and palette constraints.",
        path="methodology/art/pixel-art/SKILL.md",
    ),
    SkillMeta(
        id="art/hud-design",
        name="HUD Design",
        kind="methodology",
        nodes=("art", "art_options", "art_detail"),
        description="Readable HUD layout and feedback hierarchy.",
        path="methodology/art/hud-design/SKILL.md",
    ),
    SkillMeta(
        id="art/visual-composition",
        name="Visual Composition",
        kind="methodology",
        nodes=("art", "art_options", "art_detail"),
        description="Composition, contrast, and focal hierarchy for small games.",
        path="methodology/art/visual-composition/SKILL.md",
    ),
    SkillMeta(
        id="code/canvas",
        name="Canvas Engine",
        kind="methodology",
        nodes=("code", "repair"),
        description="Native Canvas/RAF implementation methodology.",
        path="engines/canvas.md",
    ),
    SkillMeta(
        id="code/phaser3",
        name="Phaser 3",
        kind="methodology",
        nodes=("code", "repair"),
        description="Phaser 3 scene/ticker methodology.",
        path="engines/phaser3.md",
    ),
    SkillMeta(
        id="code/pixijs",
        name="PixiJS",
        kind="methodology",
        nodes=("code", "repair"),
        description="PixiJS ticker/display-object methodology.",
        path="engines/pixijs.md",
    ),
    SkillMeta(
        id="repair/runtime-error",
        name="Runtime Error Repair",
        kind="methodology",
        nodes=("repair", "code"),
        description="Diagnose and fix runtime/pageerror failures.",
        path="methodology/repair/runtime-error/SKILL.md",
    ),
    SkillMeta(
        id="repair/gameplay-regression",
        name="Gameplay Regression Repair",
        kind="methodology",
        nodes=("repair", "code"),
        description="Fix playable-loop regressions without deleting features.",
        path="methodology/repair/gameplay-regression/SKILL.md",
    ),
    SkillMeta(
        id="playtest/observation",
        name="Playtest Observation",
        kind="methodology",
        nodes=("repair", "qa", "diagnose"),
        description="How to observe input, motion signals, and report evidence.",
        path="methodology/playtest/observation/SKILL.md",
    ),
)


@lru_cache(maxsize=1)
def list_skill_metas() -> tuple[SkillMeta, ...]:
    return _REGISTRY


def get_skill_meta(skill_id: str) -> SkillMeta | None:
    for meta in list_skill_metas():
        if meta.id == skill_id:
            return meta
    return None


def skill_bundle_hash(skill_ids: list[str] | tuple[str, ...]) -> str:
    """Hash selected skill ids + bodies for cache invalidation (P4-ready)."""
    h = hashlib.sha256()
    for skill_id in sorted(skill_ids):
        meta = get_skill_meta(skill_id)
        body = load_skill_body(meta.path) if meta else ""
        h.update(skill_id.encode("utf-8"))
        h.update(b"\0")
        h.update(body.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()
