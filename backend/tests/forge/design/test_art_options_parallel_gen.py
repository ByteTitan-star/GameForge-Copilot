"""并行生成两套美术方向再聚合。"""

from __future__ import annotations

import asyncio

import pytest

from app.forge.art_options_parallel import generate_art_options_parallel
from app.forge.guard import ContentAttacked


@pytest.mark.asyncio
async def test_generate_art_options_parallel_gathers_both() -> None:
    calls: list[str] = []

    async def complete(system: str, user: str) -> str:
        calls.append(system)
        await asyncio.sleep(0.01)
        if "TARGET=A" in system:
            return '{"id":"A","name":"纸面","summary":"层叠剪影与纸质纹理","recommended":true}'
        return '{"id":"B","name":"轨迹","summary":"残影与节奏闪动效","recommended":false}'

    out = await generate_art_options_parallel(
        system_prompt="BASE",
        user_msg="策划稿…",
        complete=complete,
    )
    assert len(out["options"]) == 2
    assert {o["id"] for o in out["options"]} == {"A", "B"}
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_generate_art_options_parallel_propagates_attack() -> None:
    async def complete(_s: str, _u: str) -> str:
        raise ContentAttacked(category="jailbreak", side="output", reason="test")

    with pytest.raises(ContentAttacked):
        await generate_art_options_parallel(
            system_prompt="BASE",
            user_msg="x",
            complete=complete,
        )
