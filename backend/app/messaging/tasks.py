"""
异步任务名与 payload 序列化（arq job 名 → RabbitMQ routing key）。

这个文件定义了 Worker 能处理的所有任务类型，以及消息的编解码格式。
它是 Worker 的"服务目录"——所有任务名、队列名、交换器名都在这里统一管理。
"""

from __future__ import annotations

import json
import uuid
from typing import Any

# ============================================================
# 1. 任务类型常量（routing key == task name）
#    这些是 Worker 能处理的所有任务类型清单
#    API / 定时器 发送消息时，必须使用这里定义的任务名
# ============================================================

# 游戏生成相关
TASK_EXECUTE_RUN = "execute_run"  # 执行游戏生成（用户首次提交需求）
TASK_RESUME_RUN = "resume_run"  # 恢复已暂停的生成（用户确认/修改策划稿后）

# 邮件发送相关
TASK_SEND_VERIFICATION = "send_verification_email"  # 发送注册验证码邮件
TASK_SEND_RESET = "send_reset_email"  # 发送密码重置邮件
TASK_SEND_NOTIFICATION = "send_notification_email"  # 发送通用通知邮件

# 定时任务相关
TASK_SCAN_SCHEDULES = "scan_schedules"  # 定时扫描到期游戏下架

# ============================================================
# 2. RabbitMQ 基础设施常量
#    定义交换器（Exchange）和队列（Queue）的名称
# ============================================================

TASK_EXCHANGE = "gameforge.tasks"  # 任务交换器：生产者发送消息到这里
TASK_QUEUE = "gameforge.worker"  # 任务队列：Worker 从此队列消费消息
TASK_DLQ = "gameforge.worker.dlq"  # 死信队列：毒消息耗尽重试后落入此处

# 消费侧重投计数（应用层 header；RabbitMQ 原生 requeue 不递增计数）
HEADER_RETRY_COUNT = "x-retry-count"

WS_EXCHANGE = "gameforge.ws"  # WebSocket 交换器：用于推送实时进度给前端

# ============================================================
# 3. 消息编解码函数
#    统一消息格式：{"task": "任务名", "payload": {...}}
# ============================================================


def encode_task(task: str, payload: dict[str, Any]) -> bytes:
    """
    将任务名和 payload 编码为字节流，用于发送到 RabbitMQ。

    参数：
        task: 任务类型（如 'execute_run'）
        payload: 任务参数（如 {'run_id': 'abc-123'}）

    返回：
        bytes: JSON 序列化后的字节流

    示例：
        encode_task('execute_run', {'run_id': 'abc-123'})
        → b'{"task":"execute_run","payload":{"run_id":"abc-123"}}'

    注意：
        default=str 确保 UUID、datetime 等类型自动转换为字符串
    """
    return json.dumps({"task": task, "payload": payload}, default=str).encode()


def decode_task(body: bytes) -> tuple[str, dict[str, Any]]:
    """
    将从 RabbitMQ 接收到的字节流解码为任务名和 payload。

    参数：
        body: 从 RabbitMQ 收到的字节流

    返回：
        tuple[str, dict]: (任务名, payload字典)

    示例：
        decode_task(b'{"task":"execute_run","payload":{"run_id":"abc-123"}}')
        → ('execute_run', {'run_id': 'abc-123'})

    注意：
        如果消息格式不对，会抛出 json.JSONDecodeError 或 KeyError
    """
    data = json.loads(body)
    return str(data["task"]), dict(data["payload"])


# ============================================================
# 4. Payload 辅助构造函数
#    统一构造标准格式的 payload，避免字段名拼写错误
# ============================================================


def run_id_payload(run_id: uuid.UUID) -> dict[str, str]:
    """
    构造执行/恢复任务的标准 payload。

    参数：
        run_id: 运行实例的 UUID

    返回：
        dict: {"run_id": "uuid字符串"}

    使用场景：
        - 调用 execute_run 时
        - 调用 resume_run 时（还需要额外字段）
    """
    return {"run_id": str(run_id)}


def resume_payload(
    run_id: uuid.UUID,
    decision: str,
    modify_text: str | None,
    command_id: uuid.UUID | None = None,
) -> dict[str, str | None]:
    """构造恢复任务（resume_run）的标准 payload。"""
    payload: dict[str, str | None] = {
        "run_id": str(run_id),
        "decision": decision,
        "modify_text": modify_text,
    }
    if command_id is not None:
        payload["command_id"] = str(command_id)
    return payload
