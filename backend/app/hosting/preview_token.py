"""Draft 多文件产物 preview token（§19.2 Artifact Path Preview Token）。

Token 绑定 game_id + version + owner，存 Redis，TTL = draft_url_ttl_s。
浏览器访问 /preview/{token}/{game_id}/{version}/ 及子资源共享同一授权上下文。
"""

from __future__ import annotations

import json
import secrets
import uuid

import redis.asyncio as redis

from app.core.config import settings

_REDIS_PREFIX = "preview:"


def _key(token: str) -> str:
    return f"{_REDIS_PREFIX}{token}"


def preview_url_path(token: str, game_id: uuid.UUID, version: int) -> str:
    """返回带尾斜杠的 preview 入口路径（配合 Vite base: './' 相对资源解析）。"""
    return f"/preview/{token}/{game_id}/{version}/"


async def mint_preview_token(
    r: redis.Redis,
    *,
    game_id: uuid.UUID,
    version: int,
    owner_id: uuid.UUID,
) -> str:
    token = secrets.token_urlsafe(32)
    payload = {
        "game_id": str(game_id),
        "version": version,
        "owner_id": str(owner_id),
    }
    await r.set(_key(token), json.dumps(payload), ex=settings.draft_url_ttl_s)
    return token


async def validate_preview_token(
    r: redis.Redis,
    token: str,
    *,
    game_id: uuid.UUID,
    version: int,
) -> bool:
    raw = await r.get(_key(token))
    if not raw:
        return False
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return False
    return payload.get("game_id") == str(game_id) and payload.get("version") == version
