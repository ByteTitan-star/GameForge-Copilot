"""QA helpers for CodeQaLoop（diagnose 等）。

【学习】主入口 diagnose_playtest_failure，见 diagnose.py（阅读顺序第 6 步）。
"""

from app.forge.qa.diagnose import diagnose_playtest_failure, fallback_diagnosis

__all__ = ["diagnose_playtest_failure", "fallback_diagnosis"]
