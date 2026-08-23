"""生成阶段人话标签与 ETA（Batch A · B-A3）。"""

from app.enums import RunPhase

# phase -> (human_label, eta_seconds)
_PHASE_META: dict[str, tuple[str, int]] = {
    RunPhase.PLAN.value: ("正在整理玩法说明", 120),
    RunPhase.ART.value: ("正在设计视觉方案", 60),
    RunPhase.CODE.value: ("正在编写游戏代码", 180),
    RunPhase.QA.value: ("正在自动试玩质检", 90),
    RunPhase.DONE.value: ("生成完成", 0),
}


def phase_start_payload(phase: str) -> dict[str, str | int]:
    """为 WS phase_start 事件生成人话标签与 ETA 附加字段。

    场景：graph 阶段切换时 ``publish_event`` 的 payload 补充。
    参数：phase - RunPhase 值字符串。
    返回：含 phase、human_label、eta_seconds 的 dict。
    """
    label, eta = _PHASE_META.get(phase, ("处理中", 60))
    return {"phase": phase, "human_label": label, "eta_seconds": eta}
