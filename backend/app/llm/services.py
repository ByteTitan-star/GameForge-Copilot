"""LLM 配置业务逻辑：CRUD + 连通测试 + 加密/掩码。

所有查询按 user_id 过滤（ownership），非本人配置 → LLM_CONFIG_NOT_FOUND。
"""

import json
from uuid import UUID

import redis.asyncio as redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import LLMProvider
from app.llm import crypto, provider
from app.llm.url_safety import validate_llm_base_url
from app.models.llm_config import UserLLMConfig
from app.models.user import User
from app.schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigCreateResp,
    LLMConfigDeleteResp,
    LLMConfigDryTestResp,
    LLMConfigPatch,
    LLMConfigResp,
    LLMConfigTestReq,
    LLMConfigTestResp,
)


def _mask(apikey: str) -> str:
    return f"{apikey[:3]}***{apikey[-3:]}" if len(apikey) > 6 else "***"


def _to_resp(cfg: UserLLMConfig) -> LLMConfigResp:
    return LLMConfigResp(
        config_id=cfg.id,
        provider=LLMProvider(cfg.provider),
        model=cfg.model,
        apikey_masked=_mask(crypto.decrypt_apikey(cfg.apikey_enc)),
        base_url=cfg.base_url,
        is_default=cfg.is_default,
    )


async def list_configs(db: AsyncSession, user: User) -> list[LLMConfigResp]:
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
    rows = (await db.scalars(stmt)).all()
    return [_to_resp(r) for r in rows]


async def list_models_for_user(
    db: AsyncSession,
    r: redis.Redis,
    user: User,
    llm_provider: LLMProvider,
) -> list[str]:
    """取用户该 provider 的配置拉 /models；Redis 短期缓存（docs/05）。"""
    cache_key = f"models:{user.id}:{llm_provider.value}"
    cached = await r.get(cache_key)
    if cached:
        try:
            return list(json.loads(cached))
        except json.JSONDecodeError:
            pass
    cfg = await db.scalar(
        select(UserLLMConfig).where(
            UserLLMConfig.user_id == user.id,
            UserLLMConfig.provider == llm_provider.value,
        )
    )
    apikey = crypto.decrypt_apikey(cfg.apikey_enc) if cfg else ""
    base_url = cfg.base_url if cfg else None
    models = await provider.list_models(llm_provider, apikey, base_url)
    await r.set(cache_key, json.dumps(models), ex=settings.models_cache_ttl_s)
    return models


async def _get_owned(db: AsyncSession, user: User, config_id: UUID) -> UserLLMConfig:
    stmt = select(UserLLMConfig).where(
        UserLLMConfig.id == config_id, UserLLMConfig.user_id == user.id
    )
    cfg = await db.scalar(stmt)
    if cfg is None:
        raise AppError(ErrorCode.LLM_CONFIG_NOT_FOUND, "配置不存在")
    return cfg


async def _unset_default(db: AsyncSession, user: User) -> None:
    await db.execute(
        update(UserLLMConfig)
        .where(UserLLMConfig.user_id == user.id, UserLLMConfig.is_default.is_(True))
        .values(is_default=False)
    )


async def create_config(
    db: AsyncSession, user: User, req: LLMConfigCreate
) -> LLMConfigCreateResp:
    """连通测试通过才保存（docs/05 §连通性测试）。openai_compat 校验 base_url。"""
    validate_llm_base_url(req.base_url)
    ok, err = await provider.test_connectivity(
        req.provider, req.apikey, req.model, req.base_url
    )
    if not ok:
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, f"连通测试失败: {err}")
    if req.is_default:
        await _unset_default(db, user)
    cfg = UserLLMConfig(
        user_id=user.id,
        provider=req.provider.value,
        model=req.model,
        apikey_enc=crypto.encrypt_apikey(req.apikey),
        base_url=req.base_url,
        is_default=req.is_default,
    )
    db.add(cfg)
    await db.commit()
    await db.refresh(cfg)
    return LLMConfigCreateResp(tested_ok=True, **_to_resp(cfg).model_dump())


async def patch_config(
    db: AsyncSession, user: User, config_id: UUID, req: LLMConfigPatch
) -> LLMConfigResp:
    cfg = await _get_owned(db, user, config_id)
    if req.model is not None:
        cfg.model = req.model
    if req.is_default is True:
        await _unset_default(db, user)
        cfg.is_default = True
    elif req.is_default is False:
        cfg.is_default = False
    await db.commit()
    await db.refresh(cfg)
    return _to_resp(cfg)


async def delete_config(
    db: AsyncSession, user: User, config_id: UUID
) -> LLMConfigDeleteResp:
    cfg = await _get_owned(db, user, config_id)
    if cfg.is_default:
        stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
        count = len((await db.scalars(stmt)).all())
        if count > 1:
            raise AppError(ErrorCode.INVALID_STATE, "删除默认配置前需先指定新默认")
    await db.delete(cfg)
    await db.commit()
    return LLMConfigDeleteResp(config_id=cfg.id)


async def test_draft_config(req: LLMConfigTestReq) -> LLMConfigDryTestResp:
    """保存前探测，不写入数据库。"""
    validate_llm_base_url(req.base_url)
    ok, err = await provider.test_connectivity(
        req.provider, req.apikey, req.model, req.base_url
    )
    return LLMConfigDryTestResp(tested_ok=ok, error=err)


async def test_config(
    db: AsyncSession, user: User, config_id: UUID
) -> LLMConfigTestResp:
    cfg = await _get_owned(db, user, config_id)
    ok, err = await provider.test_connectivity(
        LLMProvider(cfg.provider),
        crypto.decrypt_apikey(cfg.apikey_enc),
        cfg.model,
        cfg.base_url,
    )
    return LLMConfigTestResp(config_id=cfg.id, tested_ok=ok, error=err)
