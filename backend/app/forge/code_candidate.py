"""Candidate 版本分配与 promote（仅 qa_ok 后提升为 current_version）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game import Game
from app.models.game_version import GameVersion

CandidateKind = Literal["single-html", "project"]

# 单次 attempt 内 LLM 输出解析小重试（与 CodeQaLoop 外层 attempt 正交）
CODE_OUTPUT_PARSE_MAX_ATTEMPTS = 2


@dataclass
class CandidateResult:
    """单次 generate/repair + build 的结果。"""

    candidate_ready: bool
    candidate_version: int | None = None
    candidate_kind: CandidateKind | None = None
    failure_kind: Literal["build"] | None = None
    errors: list[str] = field(default_factory=list)
    extra_state: dict[str, Any] = field(default_factory=dict)


async def next_candidate_version(session: AsyncSession, game: Game) -> int:
    """分配下一个版本号，不修改 game.current_version。"""
    max_stored = await session.scalar(
        select(func.max(GameVersion.version)).where(GameVersion.game_id == game.id)
    )
    return max(int(max_stored or 0), int(game.current_version or 0)) + 1


def promote_candidate(game: Game, version: int) -> None:
    """仅在 qa_ok 后调用：把通过试玩的 candidate 提升为交付版。"""
    if version < 1:
        raise ValueError("promote_candidate requires version >= 1")
    game.current_version = version
