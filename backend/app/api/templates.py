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
    """将模板字典转为 TemplateItem 响应模型。

    作用：补全 engine、playable、play_url 等 API 字段。
    场景：模板列表接口组装单项。
    参数：row — 缓存或 loader 返回的模板字典。
    返回：TemplateItem Pydantic 模型。
    """
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
    """列出全部 forge 模板（只读）。

    作用：从缓存读取模板目录并规范化 engine 字段。
    场景：创建游戏时选择模板，无需登录。
    参数：r — Redis 客户端（模板缓存）。
    返回：ApiResponse，data 为 TemplateItem 列表。
    """
    rows = await list_templates_cached(r)
    items: list[TemplateItem] = []
    for t in rows:
        engine = await normalize_engine_id_cached(r, t.get("engine"))
        items.append(_to_item({**t, "engine": engine}))
    return ApiResponse(data=items)
