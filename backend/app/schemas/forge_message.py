import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ForgeMessageItem(BaseModel):
    """ForgeMessageItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    message_id: uuid.UUID
    game_id: uuid.UUID
    run_id: uuid.UUID | None = None
    role: Literal["user", "assistant", "system"]
    kind: str
    content: str
    metadata: dict
    created_at: datetime
