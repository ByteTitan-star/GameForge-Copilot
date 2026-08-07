"""异步任务名与 payload 序列化（arq job 名 → RabbitMQ routing key）。"""

from __future__ import annotations

import json
import uuid
from typing import Any

# routing key == task name（与旧 arq job 名一致，便于迁移）
TASK_EXECUTE_RUN = "execute_run"
TASK_RESUME_RUN = "resume_run"
TASK_SEND_VERIFICATION = "send_verification_email"
TASK_SEND_RESET = "send_reset_email"
TASK_SEND_NOTIFICATION = "send_notification_email"
TASK_SCAN_SCHEDULES = "scan_schedules"

TASK_EXCHANGE = "gameforge.tasks"
TASK_QUEUE = "gameforge.worker"

WS_EXCHANGE = "gameforge.ws"


def encode_task(task: str, payload: dict[str, Any]) -> bytes:
    return json.dumps({"task": task, "payload": payload}, default=str).encode()


def decode_task(body: bytes) -> tuple[str, dict[str, Any]]:
    data = json.loads(body)
    return str(data["task"]), dict(data["payload"])


def run_id_payload(run_id: uuid.UUID) -> dict[str, str]:
    return {"run_id": str(run_id)}


def resume_payload(
    run_id: uuid.UUID, decision: str, modify_text: str | None
) -> dict[str, str | None]:
    return {"run_id": str(run_id), "decision": decision, "modify_text": modify_text}
