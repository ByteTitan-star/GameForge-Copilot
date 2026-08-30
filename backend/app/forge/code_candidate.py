"""Candidate 版本分配与 promote（仅 qa_ok 后提升为 current_version）。

【本文件 = CodeQaLoop 阅读顺序第 5 步上半 · 约 8min】
────────────────────────────────────────
核心心智：candidate ≠ 对外交付版。

  claim_candidate_version  — code_or_repair 落盘时领号（不改 game.current_version）
  promote_candidate        — 仅 qa_ok 后由 graph.code_qa_loop_node 调用，升为 current

与 CodeQaLoop：
  execute_code_or_repair 成功 → candidate_ready + candidate_version
  子图 mark_ok → 主图 promote（带 Redis 幂等，见 idempotency.py）

同一步下半：reliability/artifact_gate.py（previewable ≠ publishable）。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.forge.reliability.idempotency import (
    get_side_effect_value,
    side_effect_key,
    try_begin_side_effect,
)
from app.models.game import Game
from app.models.game_version import GameVersion

CandidateKind = Literal["single-html", "project"]

# 单次 attempt 内 LLM 输出解析小重试（与 CodeQaLoop 外层 attempt 正交）
CODE_OUTPUT_PARSE_MAX_ATTEMPTS = 2


@dataclass
class CandidateResult:
    """单次 generate/repair + build 的结果（尚未 promote）。"""

    candidate_ready: bool  # 是否写出了可试玩候选
    candidate_version: int | None = None  # 候选版本号（≠ game.current_version）
    candidate_kind: CandidateKind | None = None  # single-html / project
    failure_kind: Literal["build"] | None = None  # 仅构建失败时标记 build
    errors: list[str] = field(default_factory=list)  # 构建/解析错误
    extra_state: dict[str, Any] = field(default_factory=dict)  # 附加回写 state 的字段


async def next_candidate_version(session: AsyncSession, game: Game) -> int:
    """分配下一个版本号，不修改 game.current_version。"""
    max_stored = await session.scalar(
        select(func.max(GameVersion.version)).where(GameVersion.game_id == game.id)
    )
    return max(int(max_stored or 0), int(game.current_version or 0)) + 1


async def claim_candidate_version(
    r: redis.Redis,
    session: AsyncSession,
    game: Game,
    *,
    run_id: uuid.UUID,
    attempt: int,
) -> tuple[int, bool]:
    """按 run+attempt 幂等领取 candidate 版本号。

    返回 (version, is_new)。重放同一 attempt 时复用已领取版本，避免重复抬号。
    """
    key = side_effect_key(run_id, "code_or_repair", f"attempt-{int(attempt)}", "save_candidate")
    existing = await get_side_effect_value(r, key)
    if existing is not None and str(existing).isdigit():
        return int(existing), False

    version = await next_candidate_version(session, game)
    if await try_begin_side_effect(r, key, value=str(version)):
        return version, True

    claimed = await get_side_effect_value(r, key)
    if claimed is not None and str(claimed).isdigit():
        return int(claimed), False
    return version, True


def promote_candidate(game: Game, version: int) -> None:
    """仅在 qa_ok 后调用：把通过试玩的 candidate 提升为交付版。"""
    if version < 1:
        raise ValueError("promote_candidate requires version >= 1")
    game.current_version = version
