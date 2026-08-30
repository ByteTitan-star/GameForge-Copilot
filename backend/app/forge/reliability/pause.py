"""可恢复暂停：status=paused + pause_reason/recovery（ADR-05）。

【阅读导读 · 本地学习用注释】
────────────────────────────────────────
「暂停」不是随便改个 status 字符串，而是一套可机器读取的表示：

  run.status = PAUSED
  checkpoint = {
    phase,                 # 停在哪（plan_confirm / qa_failed / ...）
    pause_reason,          # 为什么停（hitl / recoverable_error / user_pause ...）
    recovery?,             # 可恢复时：node / error_code / attempts / can_retry
    design_doc?, art_*, …  # 进度字段必须保留
  }

关键纪律（ADR-10）：
  任何暂停写入必须 merge 现有 checkpoint，禁止只持久化 design_doc
  把 art/code/qa 进度冲掉 —— 用 merge_pause_checkpoint，不要裸写。

主图调用点：graph._pause_hitl / _pause_recoverable。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from app.enums import PauseReason, RunStatus


class _StatusCarrier(Protocol):
    """只要带 status 字段即可（GenerationRun 或测试替身）。"""

    status: str


@dataclass(frozen=True, slots=True)
class RecoveryInfo:
    """可恢复暂停时挂在 checkpoint.recovery 上，供前端 / resume 决策。"""

    node: str  # 失败发生在哪个节点（策略名或逻辑名）
    error_code: str  # 见 reliability.errors 的 error_code
    attempts: int  # 已尝试次数
    can_retry: bool = True  # 是否建议自动/手动重试


def apply_paused_metadata(run: _StatusCarrier) -> None:
    """仅设置 status=paused，不引入新 RunStatus。"""
    run.status = RunStatus.PAUSED.value


def build_pause_checkpoint(
    *,
    phase: str,
    pause_reason: PauseReason,
    design_doc: dict[str, Any] | str | None = None,
    recovery: RecoveryInfo | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """从零构造一份暂停 checkpoint（不合并历史）。

    一般业务路径优先用 merge_pause_checkpoint，避免丢进度。
    """
    state: dict[str, Any] = {
        "phase": phase,
        "pause_reason": pause_reason.value,
    }
    if design_doc is not None:
        state["design_doc"] = design_doc
    if recovery is not None:
        state["recovery"] = asdict(recovery)
    if extra:
        state.update(extra)
    return state


def merge_pause_checkpoint(
    existing: dict[str, Any] | None,
    *,
    phase: str,
    pause_reason: PauseReason,
    design_doc: dict[str, Any] | str | None = None,
    recovery: RecoveryInfo | None = None,
    drop_keys: frozenset[str] | None = None,
) -> dict[str, Any]:
    """以现有 checkpoint 为底覆盖暂停字段，避免丢掉 art/code 进度（ADR-10）。

    默认会先 pop 掉旧的 pause_reason / recovery，再写入新的；
    其它字段（art_options、candidate_version 等）原样保留。
    """
    base = dict(existing or {})
    remove = drop_keys or frozenset({"pause_reason", "recovery"})
    for key in remove:
        base.pop(key, None)
    doc = design_doc if design_doc is not None else base.get("design_doc")
    return build_pause_checkpoint(
        phase=phase,
        pause_reason=pause_reason,
        design_doc=doc,
        recovery=recovery,
        extra={
            k: v
            for k, v in base.items()
            if k not in {"phase", "pause_reason", "recovery", "design_doc"}
        },
    )


def pause_reason_from_state(state: dict[str, Any] | None) -> PauseReason | None:
    """从 checkpoint 解析 PauseReason；缺失或非法时由调用方处理。"""
    if not state:
        return None
    raw = state.get("pause_reason")
    if raw is None:
        return None
    return PauseReason(str(raw))


def recovery_from_state(state: dict[str, Any] | None) -> dict[str, Any] | None:
    """取出 checkpoint.recovery 字典（若有）。"""
    if not state:
        return None
    recovery = state.get("recovery")
    return dict(recovery) if isinstance(recovery, dict) else None
