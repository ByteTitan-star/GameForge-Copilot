"""P1 Memory：Session Summary / Preferences / ContextBuilder。

【赶时间 · 用户偏好记忆 · 阅读顺序（约 60–75min）】
────────────────────────────────────────
第 0 步(8min)  docs/adr/ADR-02-preference-retention.md
               ← Explicit 保留 / Inferred 不覆盖 / 清偏好 / active≤50
第 1 步(10min) models/user_preference.py + api/preferences.py
               ← 表结构 + 用户手动 CRUD（显式表达入口之一）
第 2 步(12min) memory/explicit.py + inferred.py
               ← 触发词「以后/默认…」vs 弱推断；inferred 不得盖 explicit
第 3 步(12min) memory/preferences.py + llm_extract.py
               ← 正式写入路径：upsert_preferences_from_text（LLM 抽取）
第 4 步(15min) memory/context_builder.py + loader.py
               ← 如何注入 prompt；偏好是 data 不是 instruction
第 5 步(10min) graph.py 搜 _upsert_preferences_from_text / _compose_plan_input
               ← 生成时何时写、何时读
第 6 步(选读)  summary.py + refresh.py（会话摘要，非长期偏好）
               config 搜 memory_preferences*
"""

from app.forge.memory.context_builder import (
    BuiltContext,
    ContextArtifacts,
    ContextBuilder,
    ContextTurn,
    context_fingerprint,
    estimate_tokens,
)
from app.forge.memory.llm_summary import synthesize_summary_via_llm
from app.forge.memory.summary import (
    SessionSummary,
    coerce_session_summary,
    empty_session_summary,
    should_refresh_summary,
    synthesize_summary_from_turns,
)

__all__ = [
    "BuiltContext",
    "ContextArtifacts",
    "ContextBuilder",
    "ContextTurn",
    "SessionSummary",
    "coerce_session_summary",
    "context_fingerprint",
    "empty_session_summary",
    "estimate_tokens",
    "should_refresh_summary",
    "synthesize_summary_from_turns",
    "synthesize_summary_via_llm",
]
