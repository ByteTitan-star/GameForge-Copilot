from pydantic import BaseModel


class OfficialGameItem(BaseModel):
    slug: str
    title: str
    description: str
    play_url: str
    thumbnail_url: str | None = None
