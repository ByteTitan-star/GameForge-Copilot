from pydantic import BaseModel


class OfficialGameItem(BaseModel):
    """OfficialGameItem 列表项 DTO。

    场景：分页/列表 API 的单条记录结构。"""

    slug: str
    title: str
    description: str
    play_url: str
    thumbnail_url: str | None = None
