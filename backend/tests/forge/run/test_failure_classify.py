"""P5：Failure 分类增强 — LLM 不可覆盖硬规则，confidence 由系统计算。"""

from __future__ import annotations

import json

from app.core.metrics import (
    FAILURE_CLASS_OVERRIDE,
    FAILURE_CLASS_TOTAL,
    FAILURE_CLASS_UNKNOWN,
)
from app.enums import FailureClass, RunCommandType
from app.forge.failure import classify_failure, record_classification_metrics
from app.forge.hitl import allowed_commands_for


def test_qa_prompt_requests_candidate_class() -> None:
    from app.forge.prompts import QA_PROMPT
    from app.forge.qa.diagnose import fallback_diagnosis

    assert '"candidate_class"' in QA_PROMPT
    raw = fallback_diagnosis(["page never loaded"])
    assert json.loads(raw)["candidate_class"] == FailureClass.UNKNOWN.value


def test_llm_cannot_override_infra_hard_rule() -> None:
    result = classify_failure(
        errors=["sandbox control plane HTTP 503"],
        assistant_raw='{"candidate_class":"capability_mismatch","confidence":0.99}',
    )
    assert result.failure_class == FailureClass.INFRA_TRANSIENT
    assert result.classification_source == "DETERMINISTIC_RULE"
    assert result.classification_confidence == 1.0


def test_capability_validator_explains_mismatch() -> None:
    result = classify_failure(
        errors=["playtest never finished"],
        design_doc={
            "engine": {"id": "canvas"},
            "required_capabilities": {"realtime_multiplayer": True, "renderer": "canvas2d"},
        },
    )
    assert result.failure_class == FailureClass.CAPABILITY_MISMATCH
    assert result.classification_source == "CAPABILITY_VALIDATOR"
    assert result.classification_confidence == 1.0
    assert result.suggested_recovery == RunCommandType.REVISE_PLAN.value


def test_llm_assist_acceptance_when_ambiguous() -> None:
    result = classify_failure(
        errors=["win condition never observed"],
        assistant_raw=(
            '{"candidate_class":"acceptance_mismatch","confidence":0.99,"reason":"AC-05 not met"}'
        ),
    )
    assert result.failure_class == FailureClass.ACCEPTANCE_MISMATCH
    assert result.classification_source == "LLM_ASSISTED"
    assert result.classification_confidence < 1.0
    assert result.classification_confidence > 0
    assert result.suggested_recovery == RunCommandType.REVISE_PLAN.value


def test_system_ignores_llm_self_reported_confidence() -> None:
    result = classify_failure(
        errors=["unclear playtest miss"],
        assistant_raw='{"candidate_class":"implementation_defect","confidence":0.93}',
    )
    assert result.failure_class == FailureClass.IMPLEMENTATION_DEFECT
    assert result.classification_source == "LLM_ASSISTED"
    assert result.classification_confidence != 0.93


def test_weak_product_signal_stays_unknown_without_assistant() -> None:
    result = classify_failure(errors=["mock"], failure_kind="product")
    assert result.failure_class == FailureClass.UNKNOWN
    assert result.classification_confidence == 0.0
    assert result.suggested_recovery == RunCommandType.RETRY_IMPLEMENTATION.value


def test_recovery_policy_sandbox_includes_retry_infra() -> None:
    cmds = allowed_commands_for("sandbox_failed")
    assert RunCommandType.RETRY_INFRA.value in cmds
    assert RunCommandType.CANCEL_RUN.value in cmds


def test_capability_mismatch_commands_lead_with_revise_plan() -> None:
    cmds = allowed_commands_for("qa_failed", FailureClass.CAPABILITY_MISMATCH.value)
    assert cmds[0] == RunCommandType.REVISE_PLAN.value
    assert RunCommandType.CANCEL_RUN.value in cmds


def test_metrics_record_unknown_and_override() -> None:
    unknown_before = FAILURE_CLASS_UNKNOWN._value.get()
    override_before = FAILURE_CLASS_OVERRIDE._value.get()
    labeled_before = FAILURE_CLASS_TOTAL.labels(
        FailureClass.INFRA_TRANSIENT.value, "DETERMINISTIC_RULE"
    )._value.get()

    unknown = classify_failure(errors=["vague"])
    record_classification_metrics(unknown)
    hard = classify_failure(
        errors=["HTTP 503"],
        assistant_raw='{"candidate_class":"acceptance_mismatch"}',
    )
    record_classification_metrics(hard, assistant_raw='{"candidate_class":"acceptance_mismatch"}')

    assert FAILURE_CLASS_UNKNOWN._value.get() == unknown_before + 1
    assert FAILURE_CLASS_OVERRIDE._value.get() == override_before + 1
    assert (
        FAILURE_CLASS_TOTAL.labels(
            FailureClass.INFRA_TRANSIENT.value, "DETERMINISTIC_RULE"
        )._value.get()
        == labeled_before + 1
    )
