"""Forge Run 生命周期：终态判定。"""

from __future__ import annotations

from app.enums import RunStatus

_TERMINAL = frozenset(
    {
        RunStatus.FAILED.value,
        RunStatus.DONE.value,
        RunStatus.CANCELLED.value,
    }
)


def is_terminal_run_status(status: str | None) -> bool:
    return str(status or "") in _TERMINAL
