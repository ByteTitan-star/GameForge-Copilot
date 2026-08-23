"""用户偏好端点（P1 Memory）。"""

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.forge.memory import preferences as pref_store
from app.models.user_preference import UserPreference
from app.schemas.preferences import PreferenceItem, PreferenceList, PreferenceUpsert

router = APIRouter(prefix="/me/preferences", tags=["preferences"])


def _to_item(row: UserPreference) -> PreferenceItem:
    """将 UserPreference ORM 行转为 API PreferenceItem。

    作用：字段映射与序列化。
    场景：偏好列表/更新接口组装响应体。
    参数：row — 用户偏好数据库行。
    返回：PreferenceItem Pydantic 模型。
    """
    return PreferenceItem(
        id=row.id,
        category=row.category,
        key=row.key,
        value_json=row.value_json,
        source=row.source,
        confidence=row.confidence,
        status=row.status,
        updated_at=row.updated_at,
    )


@router.get("", response_model=ApiResponse[PreferenceList])
async def list_preferences(user: CurrentUser, db: DbSession) -> ApiResponse[PreferenceList]:
    """列出当前用户全部有效偏好。

    作用：读取 active 状态的 forge 记忆偏好项。
    场景：设置页展示或 forge 上下文加载。
    参数：user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data.items 为 PreferenceItem 列表。
    """
    rows = await pref_store.list_active_preferences(db, user.id)
    return ApiResponse(data=PreferenceList(items=[_to_item(r) for r in rows]))


@router.put("", response_model=ApiResponse[PreferenceItem])
async def upsert_preference(
    req: PreferenceUpsert, user: CurrentUser, db: DbSession
) -> ApiResponse[PreferenceItem]:
    """创建或更新一条用户偏好。

    作用：按 category/key upsert 偏好值，source 固定为 explicit。
    场景：用户显式修改 forge 记忆偏好。
    参数：req — 偏好写入体；user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data 为更新后的 PreferenceItem。
    """
    row = await pref_store.upsert_preference(
        db,
        user_id=user.id,
        category=req.category.strip(),
        key=req.key.strip(),
        value_json=req.value_json,
        source="explicit",
        status=req.status.strip() or "active",
    )
    await db.commit()
    return ApiResponse(data=_to_item(row))


@router.delete("", response_model=ApiResponse[dict[str, int]])
async def clear_preferences(user: CurrentUser, db: DbSession) -> ApiResponse[dict[str, int]]:
    """清空当前用户全部偏好。

    作用：删除该用户所有偏好记录。
    场景：用户重置 forge 记忆偏好。
    参数：user — 当前用户；db — 数据库会话。
    返回：ApiResponse，data.deleted 为删除条数。
    """
    deleted = await pref_store.clear_preferences(db, user.id)
    await db.commit()
    return ApiResponse(data={"deleted": deleted})
