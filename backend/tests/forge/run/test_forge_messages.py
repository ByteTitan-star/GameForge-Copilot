from uuid import UUID, uuid4

import httpx
from app.forge import state as ckpt
from app.models.forge_message import ForgeMessage
from sqlalchemy import select


async def test_forge_message_history_is_owner_scoped(
    verified_client: httpx.AsyncClient,
    auth_client: httpx.AsyncClient,
) -> None:
    game = await verified_client.post(
        "/api/v1/games", json={"title": "历史游戏", "requirement": "初始需求"}
    )
    assert game.status_code == 201, game.text
    game_id = game.json()["data"]["game_id"]

    rows = await verified_client.get(f"/api/v1/games/{game_id}/messages")
    assert rows.status_code == 200, rows.text
    assert rows.json()["data"] == []
    denied = await auth_client.get(f"/api/v1/games/{game_id}/messages")
    assert denied.status_code == 404
    invalid_cursor = await verified_client.get(
        f"/api/v1/games/{game_id}/messages", params={"before": str(uuid4())}
    )
    assert invalid_cursor.status_code == 200
    assert invalid_cursor.json()["data"] == []


async def test_create_run_persists_requirement_message(
    verified_client: httpx.AsyncClient,
    db_session,
) -> None:
    game = await verified_client.post(
        "/api/v1/games", json={"title": "对话游戏", "requirement": "初始需求"}
    )
    game_id = game.json()["data"]["game_id"]
    run = await verified_client.post(
        f"/api/v1/games/{game_id}/runs", json={"requirement": "做一个会跳跃的方块"}
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["data"]["run_id"]

    rows = await verified_client.get(f"/api/v1/games/{game_id}/messages")
    assert rows.status_code == 200, rows.text
    data = rows.json()["data"]
    assert len(data) == 1
    assert data[0]["role"] == "user"
    assert data[0]["kind"] == "requirement"
    assert data[0]["run_id"] == run_id
    assert data[0]["content"] == "做一个会跳跃的方块"

    count = await db_session.scalar(select(ForgeMessage).where(ForgeMessage.run_id == UUID(run_id)))
    assert count is not None


async def test_hitl_decision_is_persisted(
    verified_client: httpx.AsyncClient,
    redis_client,
    db_session,
) -> None:
    game = await verified_client.post(
        "/api/v1/games", json={"title": "HITL 游戏", "requirement": "初始需求"}
    )
    game_id = game.json()["data"]["game_id"]
    run = await verified_client.post(
        f"/api/v1/games/{game_id}/runs", json={"requirement": "生成一张地图"}
    )
    run_id = run.json()["data"]["run_id"]
    await ckpt.save_state(
        redis_client,
        UUID(run_id),
        {"phase": "plan_confirm", "design_doc": {"title": "地图"}},
        db_session,
    )
    from app.models.generation_run import GenerationRun

    generation_run = await db_session.get(GenerationRun, UUID(run_id))
    assert generation_run is not None
    generation_run.status = "paused"
    await db_session.commit()

    resolved = await verified_client.post(
        f"/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve",
        json={"node": "plan_confirm", "decision": "modify", "modify_text": "地图更大一些"},
    )
    assert resolved.status_code == 200, resolved.text

    rows = await verified_client.get(f"/api/v1/games/{game_id}/messages")
    data = rows.json()["data"]
    assert [item["kind"] for item in data] == ["requirement", "hitl_modify"]
    assert data[-1]["content"] == "地图更大一些"
