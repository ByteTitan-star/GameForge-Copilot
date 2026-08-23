import uuid
from datetime import datetime

from pydantic import BaseModel

from app.enums import EntryPhase, RunPhase, RunStatus


class ActiveRunItem(BaseModel):
    """ActiveRunItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    run_id: uuid.UUID
    game_id: uuid.UUID
    game_title: str
    status: RunStatus
    phase: RunPhase
    entry_phase: EntryPhase
    started_at: datetime
    ws_url: str
