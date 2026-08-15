"""收藏列表（Batch C · R7）。"""

from fastapi import APIRouter, Query

from app.auth.deps import CurrentUser, DbSession
from app.core.response import PaginatedData
from app.reactions import services
from app.schemas.reactions import PublicGameMeta

router = APIRouter(prefix="/me/favorites", tags=["reactions"])


@router.get("", response_model=PaginatedData[PublicGameMeta])
async def list_favorites(
    user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedData[PublicGameMeta]:
    rows, total = await services.list_favorites(db, user, page, size)
    return PaginatedData(data=rows, total=total, page=page, size=size)
