"""产物门禁标志（ADR-01）：previewable ≠ publishable，build_ok ≠ qa_ok。"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ArtifactGate:
    generation_success: bool
    previewable: bool
    publishable: bool
    qa_ok: bool

    def __post_init__(self) -> None:
        """校验门禁不变量：publishable 须 qa_ok，qa_ok 须 previewable。

        场景：derive_artifact_gate 构造后。
        参数：无。
        返回：无；违反时抛 ValueError。
        """
        if self.publishable and not self.qa_ok:
            raise ValueError("publishable requires qa_ok=True")
        if self.qa_ok and not self.previewable:
            raise ValueError("qa_ok requires previewable=True")

    def as_dict(self) -> dict[str, bool]:
        """序列化为 BUILD_DONE 等事件中的门禁标志 dict。

        场景：derive_artifact_gate 写入 WS 事件。
        参数：无。
        返回：四布尔字段的 dict。
        """
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
