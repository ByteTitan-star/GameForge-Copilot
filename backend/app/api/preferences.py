"""用户偏好端点（P1 Memory）。"""

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession
from app.core.response import ApiResponse
from app.forge.memory import preferences as pref_store
from app.models.user_preference import UserPreference
from app.schemas.preferences import PreferenceItem, PreferenceList, PreferenceUpsert

router = APIRouter(prefix="/me/preferences", tags=["preferences"])


def _to_item(row: UserPreference) -> PreferenceItem:
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
    rows = await pref_store.list_active_preferences(db, user.id)
    return ApiResponse(data=PreferenceList(items=[_to_item(r) for r in rows]))


@router.put("", response_model=ApiResponse[PreferenceItem])
async def upsert_preference(
    req: PreferenceUpsert, user: CurrentUser, db: DbSession
) -> ApiResponse[PreferenceItem]:
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
    deleted = await pref_store.clear_preferences(db, user.id)
    await db.commit()
    return ApiResponse(data={"deleted": deleted})
