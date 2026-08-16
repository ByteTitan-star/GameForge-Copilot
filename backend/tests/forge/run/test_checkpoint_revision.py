"""ADR-10：checkpoint Redis 缓存 revision 校验。"""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.forge import state as ckpt
from app.models.run_checkpoint import RunCheckpoint


async def test_load_state_rejects_stale_redis_revision(
    db_session: AsyncSession, redis_client
) -> None:
    run_id = uuid.uuid4()
    row = RunCheckpoint(run_id=run_id, state={"phase": "plan_confirm", "v": 2}, revision=2)
    db_session.add(row)
    await db_session.commit()

    # Stale cache: revision 1 with old payload
    await redis_client.set(
        f"run:ckpt:{run_id}",
        json.dumps({"revision": 1, "state": {"phase": "plan_confirm", "v": 1}}),
    )
    loaded = await ckpt.load_state(redis_client, run_id, db_session)
    assert loaded == {"phase": "plan_confirm", "v": 2}
