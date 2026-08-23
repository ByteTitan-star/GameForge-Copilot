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
    """将 apikey 掩码为前3+后3 可见形式。

    作用：API 响应展示，不落明文。
    场景：LLM 配置列表/详情。
    参数：apikey 明文。
    返回：掩码字符串。
    """
    return f"{apikey[:3]}***{apikey[-3:]}" if len(apikey) > 6 else "***"


_INVALID_APIKEY_MASK = "*** (密钥失效，请删除后重新添加)"
_RESAVE_APIKEY_HINT = (
    "apikey 解密失败，可能因 LLM_APIKEY_ENCRYPTION_KEY 或 JWT_SECRET 已变更，请删除该配置后重新添加"
)


def _masked_apikey(cfg: UserLLMConfig) -> str:
    """从配置行解密并掩码 apikey。

    作用：解密失败返回固定失效提示文案。
    场景：_to_resp 组装响应。
    参数：cfg 用户 LLM 配置行。
    返回：掩码或失效提示字符串。
    """
    plain = crypto.try_decrypt_apikey(cfg.apikey_enc)
    if plain is None:
        return _INVALID_APIKEY_MASK
    return _mask(plain)


def _to_resp(cfg: UserLLMConfig) -> LLMConfigResp:
    """将 ORM 配置行转为 API 响应模型。

    作用：组装 LLMConfigResp（含掩码 key）。
    场景：列表/创建/更新配置返回。
    参数：cfg UserLLMConfig。
    返回：LLMConfigResp。
    """
    return LLMConfigResp(
        config_id=cfg.id,
        provider=LLMProvider(cfg.provider),
        model=cfg.model,
        apikey_masked=_masked_apikey(cfg),
        base_url=cfg.base_url,
        is_default=cfg.is_default,
    )


async def list_configs(db: AsyncSession, user: User) -> list[LLMConfigResp]:
    """列出用户全部 LLM 配置。

    作用：按 user_id 查询并转响应模型。
    场景：GET /llm/configs。
    参数：db、user。
    返回：LLMConfigResp 列表。
    """
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user.id)
    rows = (await db.scalars(stmt)).all()
    return [_to_resp(r) for r in rows]


async def list_models_for_user(
    db: AsyncSession,
    r: redis.Redis,
    user: User,
    llm_provider: LLMProvider,
) -> list[str]:
    """拉取用户某 provider 的可用模型列表（带 Redis 缓存）。

    作用：调 provider.list_models；缓存 models:{user}:{provider}。
    场景：前端模型下拉、配置表单。
    参数：db、Redis、user、llm_provider。
    返回：模型 id 字符串列表。
    """
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
    apikey = ""
    if cfg:
        plain = crypto.try_decrypt_apikey(cfg.apikey_enc)
        apikey = plain or ""
    base_url = cfg.base_url if cfg else None
    models = await provider.list_models(llm_provider, apikey, base_url)
    await r.set(cache_key, json.dumps(models), ex=settings.models_cache_ttl_s)
    return models


async def _get_owned(db: AsyncSession, user: User, config_id: UUID) -> UserLLMConfig:
    """加载属于当前用户的配置行。

    作用：ownership 校验；非本人抛 LLM_CONFIG_NOT_FOUND。
    场景：patch/delete/test 配置前。
    参数：db、user、config_id。
    返回：UserLLMConfig。
    """
    stmt = select(UserLLMConfig).where(
        UserLLMConfig.id == config_id, UserLLMConfig.user_id == user.id
    )
    cfg = await db.scalar(stmt)
    if cfg is None:
        raise AppError(ErrorCode.LLM_CONFIG_NOT_FOUND, "配置不存在")
    return cfg


async def _unset_default(db: AsyncSession, user: User) -> None:
    """取消用户当前默认 LLM 配置标记。

    作用：将 is_default=True 的行批量置 False。
    场景：设置新默认配置前。
    参数：db、user。
    返回：None。
    """
    await db.execute(
        update(UserLLMConfig)
        .where(UserLLMConfig.user_id == user.id, UserLLMConfig.is_default.is_(True))
        .values(is_default=False)
    )


async def create_config(db: AsyncSession, user: User, req: LLMConfigCreate) -> LLMConfigCreateResp:
    """创建 LLM 配置（连通测试通过才入库）。

    作用：校验 base_url、test_connectivity、加密 apikey 后写入。
    场景：POST 创建 BYOK 配置。
    参数：db、user、req 创建请求体。
    返回：LLMConfigCreateResp（tested_ok=True）。
    """
    validate_llm_base_url(req.base_url)
    ok, err = await provider.test_connectivity(req.provider, req.apikey, req.model, req.base_url)
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
    """部分更新用户 LLM 配置。

    作用：可改 model、is_default；默认切换时先 unset 旧默认。
    场景：PATCH 配置接口。
    参数：db、user、config_id、req 补丁体。
    返回：LLMConfigResp。
    """
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


async def delete_config(db: AsyncSession, user: User, config_id: UUID) -> LLMConfigDeleteResp:
    """删除用户 LLM 配置。

    作用：默认配置且仍有其他配置时禁止删除。
    场景：DELETE 配置接口。
    参数：db、user、config_id。
    返回：LLMConfigDeleteResp。
    """
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
    """保存前探测 LLM 连通性（不写库）。

    作用：validate_llm_base_url + test_connectivity。
    场景：创建配置前的干跑测试。
    参数：req 含 provider/apikey/model/base_url。
    返回：LLMConfigDryTestResp（tested_ok、error）。
    """
    validate_llm_base_url(req.base_url)
    ok, err = await provider.test_connectivity(req.provider, req.apikey, req.model, req.base_url)
    return LLMConfigDryTestResp(tested_ok=ok, error=err)


async def test_config(db: AsyncSession, user: User, config_id: UUID) -> LLMConfigTestResp:
    """对已保存配置执行连通测试。

    作用：解密 apikey 后调 test_connectivity。
    场景：配置管理页「测试连接」。
    参数：db、user、config_id。
    返回：LLMConfigTestResp。
    """
    cfg = await _get_owned(db, user, config_id)
    plain = crypto.try_decrypt_apikey(cfg.apikey_enc)
    if plain is None:
        return LLMConfigTestResp(config_id=cfg.id, tested_ok=False, error=_RESAVE_APIKEY_HINT)
    ok, err = await provider.test_connectivity(
        LLMProvider(cfg.provider),
        plain,
        cfg.model,
        cfg.base_url,
    )
    return LLMConfigTestResp(config_id=cfg.id, tested_ok=ok, error=err)
