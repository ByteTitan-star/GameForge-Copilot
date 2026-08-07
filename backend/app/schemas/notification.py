import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationItem(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    body: str
    read: bool
    created_at: datetime


class NotificationReadResp(BaseModel):
    id: uuid.UUID
    read: bool = True
