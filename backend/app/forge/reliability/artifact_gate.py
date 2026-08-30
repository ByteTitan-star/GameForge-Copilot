"""产物门禁标志（ADR-01）：previewable ≠ publishable，build_ok ≠ qa_ok。

【本文件 = CodeQaLoop 阅读顺序第 5 步下半 · 约 7min】
────────────────────────────────────────
三标志必须分清（面试/排障高频坑）：

  generation_success / previewable  — 构建成功即可预览草稿
  qa_ok / publishable               — 仅 B 档 playtest 通过才可发布
  禁止：用静态 DOM 检查合成 qa_ok

调用点：graph.code_qa_loop_node 在 promote 成功或 exhausted HITL 时 derive_artifact_gate。
下一文件：qa/diagnose.py（第 6 步）。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ArtifactGate:
    """产物三标志；publishable 必须以 qa_ok 为前提。"""

    generation_success: bool  # 是否产出了构建结果（≈ build_ok）
    previewable: bool  # 能否预览草稿（构建成功即可）
    publishable: bool  # 能否发布（必须 qa_ok）
    qa_ok: bool  # B 档试玩是否通过

    def __post_init__(self) -> None:
        if self.publishable and not self.qa_ok:
            raise ValueError("publishable requires qa_ok=True")
        if self.qa_ok and not self.previewable:
            raise ValueError("qa_ok requires previewable=True")

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


def derive_artifact_gate(*, build_ok: bool, qa_ok: bool) -> ArtifactGate:
    """由构建与 B 档 QA 结果推导三标志。

    - 构建成功即可预览，但不得自动视为可发布
    - 仅 qa_ok 时 publishable=True
    - 禁止用静态检测合成 qa_ok
    """
    if qa_ok and not build_ok:
        raise ValueError("qa_ok requires build_ok=True")
    return ArtifactGate(
        generation_success=bool(build_ok),
        previewable=bool(build_ok),
        publishable=bool(qa_ok),
        qa_ok=bool(qa_ok),
    )
