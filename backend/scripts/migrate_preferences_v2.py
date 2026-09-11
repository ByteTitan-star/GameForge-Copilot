"""一次性迁移：user_preferences（开放键）→ user_preferences_v2（目录键，ADR-16）。

规则（issue #162：不做静默猜测映射）：
- 旧 (category, key) 经别名归一命中目录，且 value_json 中能取到合法标量
  → v2 active（source/confidence 保留，note 记 "migrated from <category>.<key>"）
- 命不中目录或值非法 → v2 archived（value 存原始 JSON 截断，note 记 unmapped 原因，
  仅供维护审计，agent 永不可见）
- 已存在同 (user_id, preference_key) 的 v2 行则跳过（可重跑）

用法：
    cd backend
    uv run python -m scripts.migrate_preferences_v2            # dry-run 预览
    uv run python -m scripts.migrate_preferences_v2 --apply    # 实际写入
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sqlalchemy import select  # noqa: E402

from app.forge.memory.catalog import slot_for, validate_candidate  # noqa: E402
from app.models.user_preference import UserPreference  # noqa: E402
from app.models.user_preference_v2 import UserPreferenceV2  # noqa: E402


def _scalar_candidates(value_json: dict[str, Any]) -> list[Any]:
    """从旧 value_json 提取候选标量：先整体（若非 dict），再各 value，再各 key。"""
    out: list[Any] = []
    if not isinstance(value_json, dict):
        out.append(value_json)
        return out
    out.extend(v for v in value_json.values() if not isinstance(v, (dict, list)))
    for v in value_json.values():
        if isinstance(v, (bool, int, float, str)):
            out.append(v)
    # 键名兜底：{"style": true} 之类键即值意的情况极少，仍保留原值优先
    return out


async def migrate(*, apply: bool) -> dict[str, int]:
    stats = {"migrated_active": 0, "unmapped_archived": 0, "skipped_existing": 0}
    from app.core import db as db_module

    async with db_module.SessionLocal() as db:
        old_rows = (await db.scalars(select(UserPreference))).all()
        for row in old_rows:
            legacy_id = f"{row.category}.{row.key}"
            slot = slot_for(legacy_id)
            pair = None
            if slot is not None:
                for cand in _scalar_candidates(dict(row.value_json or {})):
                    pair = validate_candidate(slot.key, cand)
                    if pair is not None:
                        break
            exists = await db.scalar(
                select(UserPreferenceV2).where(
                    UserPreferenceV2.user_id == row.user_id,
                    UserPreferenceV2.preference_key == (pair[0] if pair else legacy_id)[:64],
                )
            )
            if exists is not None:
                stats["skipped_existing"] += 1
                continue

            if pair is not None:
                key, value = pair
                db.add(
                    UserPreferenceV2(
                        user_id=row.user_id,
                        preference_key=key,
                        value=value,
                        value_type=slot.type if slot else "enum",
                        source=row.source if row.source in ("explicit", "inferred") else "inferred",
                        confidence=float(row.confidence or 0.5),
                        status="active",
                        note=f"migrated from {legacy_id}",
                    )
                )
                stats["migrated_active"] += 1
            else:
                raw = json.dumps(row.value_json or {}, ensure_ascii=False)[:48]
                db.add(
                    UserPreferenceV2(
                        user_id=row.user_id,
                        preference_key=legacy_id[:64],
                        value=raw,
                        value_type="string",
                        source="inferred",
                        confidence=float(row.confidence or 0.5),
                        status="archived",
                        note="unmapped legacy key, kept for audit only",
                    )
                )
                stats["unmapped_archived"] += 1
        if apply:
            await db.commit()
        else:
            await db.rollback()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际写入（默认 dry-run）")
    args = parser.parse_args()
    stats = asyncio.run(migrate(apply=args.apply))
    mode = "APPLIED" if args.apply else "DRY-RUN (rollback; pass --apply to write)"
    print(f"[migrate_preferences_v2] {mode}")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
