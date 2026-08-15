"""官方预置游戏 API（Batch A · B-A2）。"""

from fastapi import APIRouter, Query

from app.auth.deps import DbSession
from app.core.response import ApiResponse
from app.games import official as official_svc
from app.schemas.official import OfficialGameItem

router = APIRouter(prefix="/official-games", tags=["official"])


@router.get("", response_model=ApiResponse[list[OfficialGameItem]])
async def list_official_games(
    db: DbSession,
    locale: str | None = Query(None, description="zh | en"),
) -> ApiResponse[list[OfficialGameItem]]:
    rows = await official_svc.list_official_games(db, locale)
    return ApiResponse(data=[OfficialGameItem(**row) for row in rows])
