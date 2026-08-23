"""Run 终态判定：cancelled 与 failed/done 同为不可复活。"""

from app.enums import RunStatus
from app.forge.run_lifecycle import is_terminal_run_status


def test_terminal_statuses() -> None:
    assert is_terminal_run_status(RunStatus.FAILED.value)
    assert is_terminal_run_status(RunStatus.DONE.value)
    assert is_terminal_run_status(RunStatus.CANCELLED.value)
    assert not is_terminal_run_status(RunStatus.RUNNING.value)
    assert not is_terminal_run_status(RunStatus.PAUSED.value)
