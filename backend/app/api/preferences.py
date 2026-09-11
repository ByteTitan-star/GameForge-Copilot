"""用户偏好端点（ADR-16 v2：目录键 + 归档语义）。"""

from fastapi import APIRouter

from app.auth.deps import CurrentUser, DbSession
from app.core.errors import AppError, ErrorCode
from app.core.response import ApiResponse
from app.forge.memory import service as pref_service
from app.forge.memory.catalog import normalize_key, slot_for
from app.models.user_preference_v2 import UserPreferenceV2
from app.schemas.preferences import (
    PreferenceItem,
    PreferenceList,
    PreferenceRemoveResult,
    PreferenceUpsert,
)

router = APIRouter(prefix="/me/preferences", tags=["preferences"])


def _to_item(row: UserPreferenceV2) -> PreferenceItem:
    return PreferenceItem(
        id=row.id,
        preference_key=row.preference_key,
        value=row.value,
        value_type=row.value_type,
        source=row.source,
        confidence=row.confidence,
        updated_at=row.updated_at,
    )


def _require_slot(preference_key: str):
    """未知 key 直接 422（含别名归一），防止目录外键进入 API 写路径。"""
    canonical = normalize_key(preference_key)
    slot = slot_for(canonical or "")
    if slot is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"未知偏好键: {preference_key}")
    return slot


@router.get("", response_model=ApiResponse[PreferenceList])
async def list_preferences(user: CurrentUser, db: DbSession) -> ApiResponse[PreferenceList]:
    rows = await pref_service.list_active(db, user.id)
    return ApiResponse(data=PreferenceList(items=[_to_item(r) for r in rows]))


@router.put("", response_model=ApiResponse[PreferenceItem])
async def upsert_preference(
    req: PreferenceUpsert, user: CurrentUser, db: DbSession
) -> ApiResponse[PreferenceItem]:
    _require_slot(req.preference_key)
    row = await pref_service.apply_operation(
        db,
        user_id=user.id,
        op={
            "op": "set",
            "key": req.preference_key,
            "value": req.value,
            "source": "explicit",
            "confidence": 1.0,
        },
        note="api",
    )
    if row is None:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"偏好值不合法: {req.value}")
    await db.commit()
    return ApiResponse(data=_to_item(row))


@router.delete("/{preference_key}", response_model=ApiResponse[PreferenceRemoveResult])
async def remove_preference(
    preference_key: str, user: CurrentUser, db: DbSession
) -> ApiResponse[PreferenceRemoveResult]:
    canonical = _require_slot(preference_key).key
    await pref_service.apply_operation(
        db, user_id=user.id, op={"op": "remove", "key": canonical}, note="api"
    )
    await db.commit()
    return ApiResponse(data=PreferenceRemoveResult(archived=1))


@router.delete("", response_model=ApiResponse[PreferenceRemoveResult])
async def clear_preferences(
    user: CurrentUser, db: DbSession
) -> ApiResponse[PreferenceRemoveResult]:
    """清空 = 全部归档（ADR-16：不物理删除）。"""
    archived = await pref_service.clear_all(db, user.id)
    await db.commit()
    return ApiResponse(data=PreferenceRemoveResult(archived=archived))
