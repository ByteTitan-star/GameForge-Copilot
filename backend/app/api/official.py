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
    """列出全部官方预置游戏。

    作用：返回内置官方样例的 slug、标题、描述与试玩链接。
    场景：首页官方游戏区、无需登录。
    参数：db — 数据库会话；locale — 语言（zh/en）控制标题描述。
    返回：ApiResponse，data 为 OfficialGameItem 列表。
    """
    rows = await official_svc.list_official_games(db, locale)
    return ApiResponse(data=[OfficialGameItem(**row) for row in rows])
