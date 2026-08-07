"""官方预置游戏 seed（Batch A · B-A1）。

用法：cd backend && uv run python -m scripts.seed_official_games
"""

from __future__ import annotations

import asyncio

from app.core import db
from app.games.official import seed_official_games


async def main() -> None:
    async with db.SessionLocal() as session:
        n = await seed_official_games(session)
    print(f"seed_official_games: created {n} new official game(s)")


if __name__ == "__main__":
    asyncio.run(main())
