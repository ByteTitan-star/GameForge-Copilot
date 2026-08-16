"""模板只读 API（B5）。"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.deps import RedisClient
from app.core.response import ApiResponse
from app.forge.cache import list_templates_cached, normalize_engine_id_cached

router = APIRouter(prefix="/templates", tags=["templates"])


class TemplateItem(BaseModel):
    template_id: str
    title: str
    description: str
    requirement_seed: str
    tags: list[str]
    engine: str = "canvas"
    playable: bool = False
    play_url: str | None = None


def _to_item(row: dict) -> TemplateItem:
    rel = row.get("reference_artifact")
    playable = bool(rel)
    return TemplateItem(
        template_id=str(row["template_id"]),
        title=str(row["title"]),
        description=str(row.get("description") or ""),
        requirement_seed=str(row["requirement_seed"]),
        tags=list(row.get("tags") or []),
        engine=str(row.get("engine") or "canvas"),
        playable=playable,
        play_url=f"/play/template/{row['template_id']}" if playable else None,
    )


@router.get("", response_model=ApiResponse[list[TemplateItem]])
async def get_templates(r: RedisClient) -> ApiResponse[list[TemplateItem]]:
    rows = await list_templates_cached(r)
    items: list[TemplateItem] = []
    for t in rows:
        engine = await normalize_engine_id_cached(r, t.get("engine"))
        items.append(_to_item({**t, "engine": engine}))
    return ApiResponse(data=items)
