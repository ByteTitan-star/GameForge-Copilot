"""P1 FailureReport Lite + P5 三层分类（规则 / Capability / LLM 辅助）。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import (
    FAILURE_CLASS_OVERRIDE,
    FAILURE_CLASS_TOTAL,
    FAILURE_CLASS_UNKNOWN,
    FAILURE_RECOVERY_MISMATCH,
)
from app.enums import FailureClass, RunCommandType
from app.forge.capability import capability_conflicts
from app.models.failure_report import FailureReport

SUMMARY_MAX_CHARS = 500
SOURCE_RULE = "DETERMINISTIC_RULE"
SOURCE_CAPABILITY = "CAPABILITY_VALIDATOR"
SOURCE_LLM = "LLM_ASSISTED"

_INFRA_CODES = frozenset(
    {
        "provider_5xx",
        "provider_timeout",
        "provider_rate_limit",
        "sandbox_timeout",
    }
)
_RESOURCE_CODES = frozenset({"sandbox_oom"})
_POLICY_CODES = frozenset({"security_violation"})
_ASSIST_CLASSES = frozenset(
    {
        FailureClass.IMPLEMENTATION_DEFECT.value,
        FailureClass.ACCEPTANCE_MISMATCH.value,
        FailureClass.CAPABILITY_MISMATCH.value,
        FailureClass.UNKNOWN.value,
    }
)

_INFRA_RE = re.compile(
    r"(?i)(\b50[23]\b|http\s*50[23]|playwright_unavailable|chromium_unavailable|"
    r"sandbox allocation|browser launch)"
)
_IMPL_RE = re.compile(
    r"(?i)(page_error|referenceerror|typeerror|is not defined|build_error|syntaxerror)"
)
_RESOURCE_RE = re.compile(r"(?i)(\boom\b|out of memory|bundle size|quota exceeded)")
_POLICY_RE = re.compile(r"(?i)(content_blocked|policy.?denied|security_violation)")

_REDACT = (
    (re.compile(r"(?i)(bearer\s+)[a-z0-9\-._~+/]+=*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)((?:api[_-]?key|secret[_-]?key)\s*[:=]\s*)\S+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\bsk-[a-z0-9]{8,}\b"), "[REDACTED]"),
)

_SUGGESTED = {
    FailureClass.INFRA_TRANSIENT: RunCommandType.RETRY_INFRA.value,
    FailureClass.IMPLEMENTATION_DEFECT: RunCommandType.RETRY_IMPLEMENTATION.value,
    FailureClass.CAPABILITY_MISMATCH: RunCommandType.REVISE_PLAN.value,
    FailureClass.ACCEPTANCE_MISMATCH: RunCommandType.REVISE_PLAN.value,
    FailureClass.RESOURCE_EXCEEDED: RunCommandType.RETRY_INFRA.value,
    FailureClass.POLICY_SECURITY: RunCommandType.REVISE_PLAN.value,
    FailureClass.UNKNOWN: RunCommandType.RETRY_IMPLEMENTATION.value,
}


@dataclass(frozen=True)
class ClassificationResult:
    failure_class: FailureClass
    classification_source: str
    classification_confidence: float
    suggested_recovery: str


def sanitize_failure_text(text: str, *, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """脱敏并截断失败摘要文本，避免密钥泄露与过长落库。

    场景：``persist_failure_report`` 写入 FailureReport 前。
    参数：text - 原始错误/诊断文本；max_chars - 最大字符数。
    返回：脱敏后的摘要字符串。
    """
    cleaned = text
    for pat, repl in _REDACT:
        cleaned = pat.sub(repl, cleaned)
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 1] + "…"


def parse_assistant_diagnosis(raw: str | None) -> str | None:
    """只取 candidate_class；忽略 LLM 自报 confidence。"""
    data = _decode_json_object(raw)
    if data is None:
        return None
    candidate = str(data.get("candidate_class") or "").strip().lower()
    if candidate in _ASSIST_CLASSES:
        return candidate
    return None


def classify_failure(
    *,
    errors: list[str] | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    design_doc: dict[str, Any] | None = None,
    assistant_raw: str | None = None,
) -> ClassificationResult:
    """三层失败分类：规则 → 能力校验 → LLM 辅助。

    场景：CodeQa 失败或 sandbox 失败时决定 HITL 恢复命令。
    参数：
        errors - playtest/构建错误列表；
        failure_kind - infra/product 等粗分类；
        error_code - 结构化错误码；
        design_doc - 用于 capability 冲突检测；
        assistant_raw - QA 诊断 LLM 原始 JSON。
    返回：ClassificationResult，含 failure_class 与 suggested_recovery。
    """
    blob = " ".join(errors or []).strip()
    kind = (failure_kind or "").strip().lower()
    code = (error_code or "").strip().lower()
    hard = _classify_hard(blob=blob, kind=kind, code=code)
    if hard is not None:
        return _classified(hard, SOURCE_RULE, 1.0)
    if design_doc and capability_conflicts(design_doc):
        return _classified(FailureClass.CAPABILITY_MISMATCH, SOURCE_CAPABILITY, 1.0)
    assisted = parse_assistant_diagnosis(assistant_raw)
    if assisted and assisted != FailureClass.UNKNOWN.value:
        return _classified(
            FailureClass(assisted),
            SOURCE_LLM,
            _llm_confidence(error_count=len(errors or []), has_reason=bool(assisted)),
        )
    if not blob and not kind and not code:
        return _classified(FailureClass.UNKNOWN, SOURCE_RULE, 0.0)
    return _classified(FailureClass.UNKNOWN, SOURCE_RULE, 0.0)


def _classify_hard(*, blob: str, kind: str, code: str) -> FailureClass | None:
    """用正则与错误码做确定性失败分类（第一层）。

    场景：``classify_failure`` 优先路径。
    参数：blob - 拼接后的错误文本；kind - failure_kind；code - error_code。
    返回：匹配到的 FailureClass；无匹配时 None。
    """
    if code in _POLICY_CODES or (blob and _POLICY_RE.search(blob)):
        return FailureClass.POLICY_SECURITY
    if code in _RESOURCE_CODES or (blob and _RESOURCE_RE.search(blob)):
        return FailureClass.RESOURCE_EXCEEDED
    if kind == "infra" or code in _INFRA_CODES or (blob and _INFRA_RE.search(blob)):
        return FailureClass.INFRA_TRANSIENT
    if kind == "build" or (blob and _IMPL_RE.search(blob)):
        return FailureClass.IMPLEMENTATION_DEFECT
    return None


def _llm_confidence(*, error_count: int, has_reason: bool) -> float:
    """估算 LLM 辅助分类的置信度（上限 0.7）。

    场景：``classify_failure`` 采用 LLM candidate_class 时。
    参数：error_count - 错误条数；has_reason - 是否解析出有效 candidate。
    返回：0.4~0.7 的浮点置信度。
    """
    score = 0.4
    if error_count >= 1:
        score += 0.15
    if has_reason:
        score += 0.15
    return min(score, 0.7)


def _classified(
    failure_class: FailureClass, source: str, confidence: float
) -> ClassificationResult:
    """构造 ClassificationResult 并附带建议恢复命令。

    场景：各分类分支的统一出口。
    参数：failure_class - 失败类型；source - 分类来源；confidence - 置信度。
    返回：完整的 ClassificationResult。
    """
    return ClassificationResult(
        failure_class=failure_class,
        classification_source=source,
        classification_confidence=confidence,
        suggested_recovery=_SUGGESTED[failure_class],
    )


def record_classification_metrics(
    classified: ClassificationResult,
    *,
    assistant_raw: str | None = None,
    hitl_phase: str | None = None,
) -> None:
    """记录失败分类 Prometheus 指标（含 override / recovery mismatch）。

    场景：``persist_failure_report`` 分类完成后。
    参数：classified - 分类结果；assistant_raw - LLM 诊断原文；hitl_phase - 当前 HITL 阶段。
    返回：无。
    """
    FAILURE_CLASS_TOTAL.labels(
        classified.failure_class.value, classified.classification_source
    ).inc()
    if classified.failure_class is FailureClass.UNKNOWN:
        FAILURE_CLASS_UNKNOWN.inc()
    assisted = parse_assistant_diagnosis(assistant_raw)
    if (
        assisted
        and assisted != classified.failure_class.value
        and classified.classification_source != SOURCE_LLM
    ):
        FAILURE_CLASS_OVERRIDE.inc()
    if hitl_phase:
        from app.forge.hitl import allowed_commands_for

        allowed = allowed_commands_for(hitl_phase, classified.failure_class.value)
        if classified.suggested_recovery not in allowed:
            FAILURE_RECOVERY_MISMATCH.inc()


def _decode_json_object(raw: str | None) -> dict[str, Any] | None:
    """从 LLM 输出中解析 JSON 对象（容忍 Markdown 包裹）。

    场景：``parse_assistant_diagnosis`` 解析 QA 诊断。
    参数：raw - LLM 返回的字符串。
    返回：dict 或 None。
    """
    text = (raw or "").strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None


async def persist_failure_report(
    db: AsyncSession,
    *,
    run_id: uuid.UUID,
    errors: list[str] | None = None,
    failure_kind: str | None = None,
    error_code: str | None = None,
    attempt_count: int = 1,
    failure_stage: str = "PLAYTEST",
    qa_diagnosis: str = "",
    candidate_revision_id: str | None = None,
    design_doc: dict[str, Any] | None = None,
    hitl_phase: str | None = None,
) -> FailureReport:
    """分类失败原因并持久化 FailureReport 行。

    场景：CodeQa 耗尽或 sandbox 失败进入 qa_failed/sandbox_failed HITL。
    参数：run_id、errors、failure_kind、error_code、attempt_count、failure_stage、
          qa_diagnosis、candidate_revision_id、design_doc、hitl_phase。
    返回：已 flush 的 FailureReport ORM 实例。
    """
    classified = classify_failure(
        errors=errors or [],
        failure_kind=failure_kind,
        error_code=error_code,
        design_doc=design_doc,
        assistant_raw=qa_diagnosis,
    )
    record_classification_metrics(classified, assistant_raw=qa_diagnosis, hitl_phase=hitl_phase)
    summaries = [sanitize_failure_text(item) for item in (errors or []) if item]
    if qa_diagnosis.strip():
        summaries.append(sanitize_failure_text(qa_diagnosis))
    summary = sanitize_failure_text("; ".join(summaries) or classified.failure_class.value)
    row = FailureReport(
        run_id=run_id,
        candidate_revision_id=candidate_revision_id,
        failure_class=classified.failure_class.value,
        classification_source=classified.classification_source,
        classification_confidence=classified.classification_confidence,
        failure_stage=failure_stage,
        attempt_count=attempt_count,
        attempts=[{"attempt": attempt_count, "stage": failure_stage, "summary": summary}],
        diagnosis={"summary": summary, "suggested_recovery": classified.suggested_recovery},
        evidence={"errors": summaries, "failure_kind": failure_kind, "error_code": error_code},
    )
    db.add(row)
    await db.flush()
    return row
