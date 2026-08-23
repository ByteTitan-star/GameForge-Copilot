"""Skill 元数据与加载结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SkillKind = Literal["policy", "methodology"]


@dataclass(frozen=True)
class SkillMeta:
    id: str
    name: str
    kind: SkillKind
    nodes: tuple[str, ...]
    description: str
    path: str  # relative to skills package root


@dataclass(frozen=True)
class LoadedSkill:
    id: str
    name: str
    kind: SkillKind
    body: str


@dataclass(frozen=True)
class ResolvedSkills:
    policy: tuple[LoadedSkill, ...]
    methodology: tuple[LoadedSkill, ...]
    loaded_body_count: int

    def methodology_text(self) -> str:
        """拼接所有 Methodology Skill 正文供 prompt 注入。

        场景：build_*_prompt 组装附录。
        参数：无。
        返回：带 Skill id 标题的多段文本。
        """
        parts = [f"【Skill:{s.id}】\n{s.body}" for s in self.methodology if s.body]
        return "\n\n".join(parts)

    def policy_text(self) -> str:
        """拼接所有 Policy Skill 正文供 prompt 注入。

        场景：code/plan prompt 强制约束段。
        参数：无。
        返回：带 Policy id 标题的多段文本。
        """
        parts = [f"【Policy:{s.id}】\n{s.body}" for s in self.policy if s.body]
        return "\n\n".join(parts)
