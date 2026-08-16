"""生成方法论 skill 文本（docs/03）；非玩法硬编码。

P2：Platform Policy（强制）与 Agent Skills / Methodology（可选）分层；
节点通过 ``resolve_skills_for_node`` 做 Progressive Disclosure。
"""

from app.forge.skills.catalog import (
    catalog_skill_bundle_hash,
    get_skill_meta,
    list_skill_metas,
    skill_bundle_hash,
)
from app.forge.skills.loader import load_skill, load_skill_body, skills_root
from app.forge.skills.models import LoadedSkill, ResolvedSkills, SkillMeta
from app.forge.skills.router import resolve_skills_for_node

__all__ = [
    "LoadedSkill",
    "ResolvedSkills",
    "SkillMeta",
    "catalog_skill_bundle_hash",
    "get_skill_meta",
    "list_skill_metas",
    "load_skill",
    "load_skill_body",
    "resolve_skills_for_node",
    "skill_bundle_hash",
    "skills_root",
]
