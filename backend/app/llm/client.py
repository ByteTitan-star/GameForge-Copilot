"""LLM 调用门面：取用户配置→解密→provider.complete→record_usage。

明文 key 仅内存单次调用生命周期，不落日志（docs/05）。测试 monkeypatch call_llm。
"""

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin import services as admin_services
from app.auth.ratelimit import check_rate_limit
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.langfuse import observe_generation
from app.core.metrics import LLM_CALLS, LLM_TOKENS
from app.enums import LLMProvider, Role
from app.forge.reliability.idempotency import side_effect_key
from app.llm import circuit, crypto, provider
from app.llm.provider import StreamChunk
from app.models.llm_config import UserLLMConfig
from app.models.user import User
from app.notify import services as notify_services
from app.usage import quota as quota_mod
from app.usage.store import get_system_usage, get_user_usage, record_usage


def _usage_idem_key(
    *,
    user_id: uuid.UUID,
    run_id: uuid.UUID | None,
    system: str,
    user_msg: str,
    content: str,
    input_tokens: int,
    output_tokens: int,
) -> str:
    digest = hashlib.sha256(
        f"{system}\0{user_msg}\0{content}\0{input_tokens}\0{output_tokens}".encode()
    ).hexdigest()[:24]
    scope = run_id or user_id
    return side_effect_key(scope, "llm", digest, "usage")


async def _get_config(
    db: AsyncSession, user_id: uuid.UUID, config_id: uuid.UUID | None
) -> UserLLMConfig:
    stmt = select(UserLLMConfig).where(UserLLMConfig.user_id == user_id)
    if config_id is not None:
        stmt = stmt.where(UserLLMConfig.id == config_id)
    else:
        stmt = stmt.where(UserLLMConfig.is_default.is_(True))
    cfg = await db.scalar(stmt)
    if cfg is None:
        raise AppError(ErrorCode.LLM_CONFIG_INVALID, "无可用 LLM 配置")
    return cfg


async def _maybe_quota_alert(db: AsyncSession, r: redis.Redis, user_id: uuid.UUID) -> None:
    daily_default, _, rate = await admin_services.get_effective_limits(db)
    _ = rate
    daily = await quota_mod.get_user_daily_limit(r, user_id, daily_default)
    usage = await get_user_usage(r, user_id, daily)
    if usage.quota.remaining > 0:
        return
    day = f"{datetime.now(UTC):%Y-%m-%d}"
    if not await quota_mod.mark_quota_alerted(r, user_id, day):
        return
    user = await db.get(User, user_id)
    if user is None:
        return
    await notify_services.notify_user(
        db,
        user.id,
        kind="quota",
        title="GameForge 日 token 配额已耗尽",
        body=f"你今日配额 {daily} tokens 已用尽，生成将挂起直至次日重置。",
        email=user.email,
    )


async def _maybe_system_alert(db: AsyncSession, r: redis.Redis) -> None:
    """系统日用量超阈值 → 通知全体 admin（当日一次）。"""
    sys_u = await get_system_usage(r)
    used = sys_u.today.input_tokens + sys_u.today.output_tokens
    if used < settings.system_daily_token_alert:
        return
    day = f"{datetime.now(UTC):%Y-%m-%d}"
    key = f"quota:sys_alerted:{day}"
    if not await r.set(key, "1", nx=True, ex=86400):
        return
    admins = (
        await db.scalars(
            select(User).where(User.role == Role.ADMIN.value, User.disabled.is_(False))
        )
    ).all()
    for admin in admins:
        await notify_services.notify_user(
            db,
            admin.id,
            kind="system_quota",
            title="系统日 token 用量告警",
            body=(f"系统今日用量 {used} 已超过阈值 {settings.system_daily_token_alert}。"),
            email=admin.email,
        )


async def _invoke_llm(
    prov: LLMProvider,
    apikey: str,
    model: str,
    system: str,
    user_msg: str,
    base_url: str | None,
    trace_meta: dict[str, str],
    *,
    kind: str = "chat",
    max_tokens: int | None = None,
) -> provider.LLMCompletion:
    """执行 provider.complete 并挂 langfuse generation 观测。

    失败时把 generation 标 level=ERROR 后 re-raise（错误计数交回 call_llm 统一处理）。
    """
    with observe_generation(
        model=model,
        provider=prov.value,
        system=system,
        user_msg=user_msg,
        kind=kind,
        metadata=trace_meta,
    ) as gen:
        try:
            result = await provider.complete(
                prov, apikey, model, system, user_msg, base_url=base_url, max_tokens=max_tokens
            )
        except Exception:
            if gen is not None:
                gen.update(level="ERROR", status_message="llm call failed")
            raise
        if gen is not None:
            gen.update(
                output=result.content,
                usage_details={
                    "input": result.usage.input_tokens,
                    "output": result.usage.output_tokens,
                },
            )
    return result


async def call_llm(
    db: AsyncSession,
    r: redis.Redis,
    user_id: uuid.UUID,
    config_id: uuid.UUID | None,
    system: str,
    user_msg: str,
    *,
    game_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    kind: str = "chat",
    max_tokens: int | None = None,
) -> tuple[provider.LLMCompletion, LLMProvider]:
    _, _, rate = await admin_services.get_effective_limits(db)
    await check_rate_limit(r, f"rl:llm:{user_id}", rate, 60)

    cfg = await _get_config(db, user_id, config_id)
    apikey = crypto.decrypt_apikey(cfg.apikey_enc)
    prov = LLMProvider(cfg.provider)
    cb_key = circuit.circuit_key(user_id, prov, cfg.base_url)
    await circuit.assert_circuit_closed(r, cb_key)
    trace_meta: dict[str, str] = {"user_id": str(user_id)}
    if game_id is not None:
        trace_meta["game_id"] = str(game_id)
    if run_id is not None:
        trace_meta["run_id"] = str(run_id)
    try:
        result = await _invoke_llm(
            prov,
            apikey,
            cfg.model,
            system,
            user_msg,
            cfg.base_url,
            trace_meta,
            kind=kind,
            max_tokens=max_tokens,
        )
    except Exception:
        LLM_CALLS.labels(prov.value, "error").inc()
        await circuit.record_failure(r, cb_key)
        raise
    await circuit.record_success(r, cb_key)
    LLM_CALLS.labels(prov.value, "ok").inc()
    LLM_TOKENS.labels(prov.value, "input").inc(result.usage.input_tokens)
    LLM_TOKENS.labels(prov.value, "output").inc(result.usage.output_tokens)
    await record_usage(
        r,
        user_id,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        game_id=game_id,
        run_id=run_id,
        idempotency_key=_usage_idem_key(
            user_id=user_id,
            run_id=run_id,
            system=system,
            user_msg=user_msg,
            content=result.content,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
        ),
    )
    await _maybe_quota_alert(db, r, user_id)
    await _maybe_system_alert(db, r)
    # 返回 LLMCompletion（含 finish_reason）与 provider，供事件/日志使用。
    return result, prov


async def call_llm_stream(
    db: AsyncSession,
    r: redis.Redis,
    user_id: uuid.UUID,
    config_id: uuid.UUID | None,
    system: str,
    user_msg: str,
    *,
    game_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    kind: str = "chat",
    max_tokens: int | None = None,
) -> AsyncIterator[StreamChunk]:
    """流式版 call_llm：逐 token yield StreamChunk（末帧带 usage）。

    与 call_llm 对齐：限流在流开始前；record_usage/配额告警在流正常结束后（usage 末尾才确定）。
    observe_generation 包整个流循环，末尾填 output+usage。CancelledError（审核中断）
    会进 BaseException 分支标 gen=ERROR 后重新抛出——不吞，保证取消语义不被破坏。

    注意：审核中断（CancelledError）时不记 usage，provider 端已计部分 output token，
    业务侧按「内容被截断」接受不记账。
    """
    _, _, rate = await admin_services.get_effective_limits(db)
    await check_rate_limit(r, f"rl:llm:{user_id}", rate, 60)

    cfg = await _get_config(db, user_id, config_id)
    apikey = crypto.decrypt_apikey(cfg.apikey_enc)
    prov = LLMProvider(cfg.provider)
    cb_key = circuit.circuit_key(user_id, prov, cfg.base_url)
    await circuit.assert_circuit_closed(r, cb_key)
    trace_meta: dict[str, str] = {"user_id": str(user_id)}
    if game_id is not None:
        trace_meta["game_id"] = str(game_id)
    if run_id is not None:
        trace_meta["run_id"] = str(run_id)

    accumulated: list[str] = []
    usage_acc = provider.Usage()
    gen: Any = None
    try:
        with observe_generation(
            model=cfg.model,
            provider=prov.value,
            system=system,
            user_msg=user_msg,
            kind=kind,
            metadata=trace_meta,
        ) as gen:
            async for chunk in provider.complete_stream(
                prov,
                apikey,
                cfg.model,
                system,
                user_msg,
                cfg.base_url,
                max_tokens=max_tokens,
            ):
                if chunk.delta:
                    accumulated.append(chunk.delta)
                    yield chunk
                if chunk.usage is not None:
                    usage_acc = chunk.usage
            if gen is not None:
                gen.update(
                    output="".join(accumulated),
                    usage_details={
                        "input": usage_acc.input_tokens,
                        "output": usage_acc.output_tokens,
                    },
                )
        # 流正常结束才记账（usage 此刻才确定）
        await circuit.record_success(r, cb_key)
        LLM_CALLS.labels(prov.value, "ok").inc()
        LLM_TOKENS.labels(prov.value, "input").inc(usage_acc.input_tokens)
        LLM_TOKENS.labels(prov.value, "output").inc(usage_acc.output_tokens)
        full_text = "".join(accumulated)
        await record_usage(
            r,
            user_id,
            input_tokens=usage_acc.input_tokens,
            output_tokens=usage_acc.output_tokens,
            game_id=game_id,
            run_id=run_id,
            idempotency_key=_usage_idem_key(
                user_id=user_id,
                run_id=run_id,
                system=system,
                user_msg=user_msg,
                content=full_text,
                input_tokens=usage_acc.input_tokens,
                output_tokens=usage_acc.output_tokens,
            ),
        )
        await _maybe_quota_alert(db, r, user_id)
        await _maybe_system_alert(db, r)
    except BaseException as exc:
        # CancelledError（审核中断）与 httpx 异常都走这里；不记账，标 trace 失败。
        LLM_CALLS.labels(prov.value, "error").inc()
        # 熔断只统计真实故障；取消/中断不计入，避免误开熔断
        if isinstance(exc, Exception):
            await circuit.record_failure(r, cb_key)
        if gen is not None:
            gen.update(level="ERROR", status_message="llm stream aborted")
        raise
