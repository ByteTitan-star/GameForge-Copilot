import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    """NotificationItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    id: uuid.UUID
    kind: str
    title: str
    body: str
    read: bool
    created_at: datetime


class NotificationReadResp(BaseModel):
    """NotificationReadResp API 响应体。

    场景：对应端点成功响应 data 字段。"""

    id: uuid.UUID
    read: bool = True
