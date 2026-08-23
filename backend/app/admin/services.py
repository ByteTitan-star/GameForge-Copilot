"""管理后台：用户管理 + 全局设置 + 审计 + 已发布游戏列表（admin）。"""

import uuid
from datetime import datetime

import redis.asyncio as redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.enums import GameStatus, Role
from app.llm import crypto
from app.models.audit_log import AuditLog
from app.models.game import Game
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.schemas.admin import AdminAuditLlmSettings, AdminSettings
from app.usage import quota as quota_mod

_LIMITS_KEY = "limits"
_GENERAL_KEY = "general"
_AUDIT_LLM_KEY = "audit_llm"


def _mask_apikey(apikey: str) -> str:
    """将 API Key 脱敏为前 3 + *** + 后 3 位。

    作用：避免在 admin 设置页回显完整密钥。
    场景：get_audit_llm_settings_view 构造 AdminAuditLlmSettings 时调用。
    参数：apikey - 明文 API Key。
    返回：脱敏后的字符串；长度 ≤6 时返回 "***"。
    """
    return f"{apikey[:3]}***{apikey[-3:]}" if len(apikey) > 6 else "***"


async def get_admin_contact_email(db: AsyncSession) -> str:
    """解析管理员联系邮箱（多级回退）。

    作用：返回用于禁用账号提示、反馈邮件等场景的管理员邮箱。
    场景：disabled_user_message、submit_feedback、get_settings 等需要联系管理员时调用。
    参数：db - 异步数据库会话。
    返回：邮箱字符串；均无配置时回退 "admin@example.com"。
    """
    row = await db.get(SystemSetting, _GENERAL_KEY)
    if row is not None:
        contact = (row.value or {}).get("admin_contact_email", "").strip()
        if contact:
            return contact
    if settings.admin_contact_email.strip():
        return settings.admin_contact_email.strip()
    admins = await list_admin_emails(db)
    if admins:
        return admins[0]
    return "admin@example.com"


async def disabled_user_message(db: AsyncSession) -> str:
    """生成禁用账号登录时的用户提示文案。

    作用：拼接包含管理员邮箱的违规解封说明。
    场景：auth 登录校验发现 user.disabled 时返回给前端。
    参数：db - 异步数据库会话。
    返回：完整提示字符串。
    """
    contact = await get_admin_contact_email(db)
    return f"当前账号已违规，请联系管理员<{contact}>申请解封"


async def get_audit_llm_config(db: AsyncSession) -> dict:
    """读取审核模型生效配置（含明文 apikey）。

    作用：合并 DB system_settings 与 env 默认值，解密 apikey_enc。
    场景：guard.build_guard（worker 侧）与 admin 测试端点共用；DB 异常时 guard 侧需自行回退 env。
    参数：db - 异步数据库会话。
    返回：dict，含 enabled、provider、model、apikey、base_url。
    """
    row = await db.get(SystemSetting, _AUDIT_LLM_KEY)
    v = (row.value or {}) if row is not None else {}
    apikey_enc = v.get("apikey_enc", "")
    apikey = crypto.decrypt_apikey(apikey_enc) if apikey_enc else settings.audit_apikey
    return {
        "enabled": bool(v.get("enabled", settings.audit_enabled)),
        "provider": str(v.get("provider") or settings.audit_provider),
        "model": str(v.get("model") or settings.audit_model).strip(),
        "apikey": apikey,
        "base_url": str(v.get("base_url") or settings.audit_base_url),
    }


async def get_audit_llm_settings_view(db: AsyncSession) -> AdminAuditLlmSettings:
    """构造 admin 设置页审核模型回显（apikey 脱敏）。

    作用：将生效配置转为 AdminAuditLlmSettings，apikey 一律 masked。
    场景：get_settings 组装 AdminSettings 时调用。
    参数：db - 异步数据库会话。
    返回：AdminAuditLlmSettings 实例；无 key 时 apikey 为空串。
    """
    cfg = await get_audit_llm_config(db)
    return AdminAuditLlmSettings(
        enabled=cfg["enabled"],
        provider=cfg["provider"],
        model=cfg["model"],
        apikey=_mask_apikey(cfg["apikey"]) if cfg["apikey"] else "",
        base_url=cfg["base_url"],
    )


async def _active_admin_count(db: AsyncSession) -> int:
    """统计未禁用的管理员账号数量。

    作用：防止删除或降级唯一可用管理员。
    场景：patch_user、delete_user 变更角色或禁用状态前校验。
    参数：db - 异步数据库会话。
    返回：可用管理员人数整数。
    """
    return int(
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.role == Role.ADMIN.value,
                User.disabled.is_(False),
            )
        )
        or 0
    )


async def list_users(db: AsyncSession, page: int, size: int) -> tuple[list[User], int]:
    """分页列出全部用户。

    作用：admin 用户管理列表数据源。
    场景：GET /admin/users 路由调用。
    参数：db - 数据库会话；page - 页码（从 1 起）；size - 每页条数。
    返回：(用户列表, 总条数) 元组。
    """
    base = select(User)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(User.created_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def user_daily_limits(r: redis.Redis, users: list[User]) -> dict[uuid.UUID, int | None]:
    """批量读取用户日 token 限额覆盖值。

    作用：从 Redis quota:user:{uid} 拉取各用户自定义日限额。
    场景：admin 用户列表展示每人配额覆盖时调用。
    参数：r - Redis 客户端；users - 待查询用户列表。
    返回：user_id → 限额整数或 None（无覆盖）的映射。
    """
    out: dict[uuid.UUID, int | None] = {}
    for u in users:
        raw = await r.get(f"quota:user:{u.id}")
        out[u.id] = int(raw) if raw is not None else None
    return out


async def patch_user(
    db: AsyncSession,
    r: redis.Redis,
    admin: User,
    user_id: uuid.UUID,
    role: Role | None,
    disabled: bool | None,
    daily_token_limit: int | None = None,
    *,
    set_daily_limit: bool = False,
) -> User:
    """管理员修改用户角色、禁用状态或日 token 限额。

    作用：更新用户字段并写 audit_logs；可选设置 Redis 配额覆盖。
    场景：PATCH /admin/users/{id} 路由调用。
    参数：db - 数据库会话；r - Redis；admin - 操作者；user_id - 目标用户；
        role/disabled/daily_token_limit - 待更新字段；set_daily_limit - 是否写入配额覆盖。
    返回：更新后的 User；不存在或违反管理员保留规则时抛 AppError。
    """
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "用户不存在")
    if disabled is True and user.id == admin.id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能禁用当前登录的管理员账号")
    if (
        role is not None
        and role != Role.ADMIN
        and user.role == Role.ADMIN.value
        and await _active_admin_count(db) <= 1
    ):
        raise AppError(ErrorCode.VALIDATION_ERROR, "至少保留一名可用管理员")
    detail: dict = {}
    if role is not None:
        user.role = role.value
        detail["role"] = role.value
    if disabled is not None:
        user.disabled = disabled
        detail["disabled"] = disabled
    if set_daily_limit:
        await quota_mod.set_user_daily_limit(r, user_id, daily_token_limit)
        detail["daily_token_limit"] = daily_token_limit
    db.add(AuditLog(actor_id=admin.id, action="update_user", target=str(user_id), detail=detail))
    await db.commit()
    return user


async def delete_user(
    db: AsyncSession,
    r: redis.Redis,
    admin: User,
    user_id: uuid.UUID,
) -> None:
    """管理员删除用户账号。

    作用：物理删除用户行、记审计日志并清除 Redis 配额键。
    场景：DELETE /admin/users/{id} 路由调用。
    参数：db - 数据库会话；r - Redis；admin - 操作者；user_id - 目标用户 ID。
    返回：无；不可删自己或唯一管理员时抛 AppError。
    """
    user = await db.get(User, user_id)
    if user is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "用户不存在")
    if user.id == admin.id:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能删除当前登录的管理员账号")
    if user.role == Role.ADMIN.value and await _active_admin_count(db) <= 1:
        raise AppError(ErrorCode.VALIDATION_ERROR, "至少保留一名可用管理员")
    email = user.email
    await db.delete(user)
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="delete_user",
            target=str(user_id),
            detail={"email": email},
        )
    )
    await db.commit()
    await r.delete(f"quota:user:{user_id}")


async def get_settings(db: AsyncSession) -> AdminSettings:
    """读取全局 admin 设置（限额、联系邮箱、审核模型回显）。

    作用：聚合 DB 与环境变量中的生效配置。
    场景：GET /admin/settings 路由调用。
    参数：db - 异步数据库会话。
    返回：AdminSettings 实例。
    """
    daily, monthly, rate = await get_effective_limits(db)
    return AdminSettings(
        default_daily_token_limit=daily,
        default_monthly_token_limit=monthly,
        default_rate_limit_per_min=rate,
        admin_contact_email=await get_admin_contact_email(db),
        audit_llm=await get_audit_llm_settings_view(db),
    )


async def update_settings(db: AsyncSession, admin: User, req: AdminSettings) -> AdminSettings:
    """管理员更新全局设置并记审计日志。

    作用：写入 limits/general/audit_llm 三类 system_settings。
    场景：PUT /admin/settings 路由调用。
    参数：db - 数据库会话；admin - 操作者；req - 新设置体。
    返回：提交后的 AdminSettings（即 req）。
    """
    row = await db.get(SystemSetting, _LIMITS_KEY)
    value = {
        "default_daily_token_limit": req.default_daily_token_limit,
        "default_monthly_token_limit": req.default_monthly_token_limit,
        "default_rate_limit_per_min": req.default_rate_limit_per_min,
    }
    if row is None:
        row = SystemSetting(key=_LIMITS_KEY, value=value, updated_by=admin.id)
        db.add(row)
    else:
        row.value = value
        row.updated_by = admin.id
    general = await db.get(SystemSetting, _GENERAL_KEY)
    general_value = {"admin_contact_email": req.admin_contact_email.strip()}
    if general is None:
        db.add(SystemSetting(key=_GENERAL_KEY, value=general_value, updated_by=admin.id))
    else:
        general.value = general_value
        general.updated_by = admin.id
    audit_value: dict | None = None
    if req.audit_llm is not None:
        audit_value = await _merge_audit_llm_value(db, req.audit_llm)
        audit_row = await db.get(SystemSetting, _AUDIT_LLM_KEY)
        if audit_row is None:
            db.add(SystemSetting(key=_AUDIT_LLM_KEY, value=audit_value, updated_by=admin.id))
        else:
            audit_row.value = audit_value
            audit_row.updated_by = admin.id
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="update_settings",
            target=_LIMITS_KEY,
            detail={
                **value,
                **general_value,
                # 审核模型只记非敏感字段，apikey 任何形态都不进审计日志
                **({"audit_llm": _audit_log_detail(req.audit_llm)} if req.audit_llm else {}),
            },
        )
    )
    await db.commit()
    return req


async def _merge_audit_llm_value(db: AsyncSession, req: AdminAuditLlmSettings) -> dict:
    """合并审核模型 DB 存储值（处理 apikey 加密与保留）。

    作用：apikey 为空或含 *** 时保留旧密文，否则加密新 key 写入。
    场景：update_settings 更新 audit_llm 分支时调用。
    参数：db - 数据库会话；req - 提交的审核模型设置。
    返回：可写入 SystemSetting.value 的 dict。
    """
    existing = await db.get(SystemSetting, _AUDIT_LLM_KEY)
    old_enc = (existing.value or {}).get("apikey_enc", "") if existing else ""
    apikey = req.apikey.strip()
    apikey_enc = old_enc if not apikey or "***" in apikey else crypto.encrypt_apikey(apikey)
    return {
        "enabled": req.enabled,
        "provider": req.provider,
        "model": req.model.strip(),
        "apikey_enc": apikey_enc,
        "base_url": req.base_url.strip(),
    }


def _audit_log_detail(req: AdminAuditLlmSettings) -> dict:
    """构造 audit_log detail 中的审核模型快照（不含敏感字段）。

    作用：记录 enabled/provider/model/base_url 及 apikey 是否变更。
    场景：update_settings 写 AuditLog 时嵌入 detail。
    参数：req - 提交的审核模型设置。
    返回：可序列化的 dict，绝不包含 apikey 明文或密文。
    """
    return {
        "enabled": req.enabled,
        "provider": req.provider,
        "model": req.model,
        "base_url": req.base_url,
        "apikey_changed": bool(req.apikey.strip()) and "***" not in req.apikey,
    }


async def get_effective_limits(db: AsyncSession) -> tuple[int, int, int]:
    """解析生效的全局 token 限额与速率限制。

    作用：DB system_settings limits 优先，缺省回退 env 配置。
    场景：配额校验、get_settings、用户列表默认值等。
    参数：db - 异步数据库会话。
    返回：(日 token 限额, 月 token 限额, 每分钟请求数) 三元组。
    """
    row = await db.get(SystemSetting, _LIMITS_KEY)
    if row is not None:
        v = row.value or {}
        return (
            int(v.get("default_daily_token_limit", settings.default_daily_token_limit)),
            int(v.get("default_monthly_token_limit", settings.default_monthly_token_limit)),
            int(v.get("default_rate_limit_per_min", settings.default_rate_limit_per_min)),
        )
    return (
        settings.default_daily_token_limit,
        settings.default_monthly_token_limit,
        settings.default_rate_limit_per_min,
    )


async def list_audit_logs(db: AsyncSession, page: int, size: int) -> tuple[list[AuditLog], int]:
    """分页列出管理员审计日志。

    作用：按创建时间倒序返回 audit_logs 记录。
    场景：GET /admin/audit-logs 路由调用。
    参数：db - 数据库会话；page - 页码；size - 每页条数。
    返回：(AuditLog 列表, 总条数) 元组。
    """
    base = select(AuditLog)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(AuditLog.created_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def list_admin_games(
    db: AsyncSession,
    status: GameStatus | None,
    page: int,
    size: int,
) -> tuple[list[Game], int]:
    """分页列出管理员可见的已发布/管理态游戏。

    作用：筛选 published/taken_down/submitted/reviewing，不含 draft。
    场景：GET /admin/games 路由调用。
    参数：db - 数据库会话；status - 可选状态过滤；page/size - 分页参数。
    返回：(Game 列表, 总条数)；非法 status 抛 AppError。
    """
    allowed = {
        GameStatus.PUBLISHED,
        GameStatus.TAKEN_DOWN,
        GameStatus.SUBMITTED,
        GameStatus.REVIEWING,
    }
    base = select(Game).where(Game.status.in_([s.value for s in allowed]))
    if status is not None:
        if status not in allowed:
            raise AppError(ErrorCode.VALIDATION_ERROR, "admin 不可按此状态筛选草稿")
        base = select(Game).where(Game.status == status.value)
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    rows = (
        await db.scalars(
            base.order_by(Game.updated_at.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return list(rows), int(total or 0)


async def list_admin_emails(db: AsyncSession) -> list[str]:
    """列出所有未禁用管理员的邮箱。

    作用：供联系邮箱多级回退的最后一级数据源。
    场景：get_admin_contact_email 无 DB/env 配置时调用。
    参数：db - 异步数据库会话。
    返回：邮箱字符串列表。
    """
    rows = (
        await db.scalars(
            select(User).where(User.role == Role.ADMIN.value, User.disabled.is_(False))
        )
    ).all()
    return [u.email for u in rows]


async def patch_game_schedule(
    db: AsyncSession,
    admin: User,
    game_id: uuid.UUID,
    scheduled_take_down_at: datetime | None,
    scheduled_publish_at: datetime | None,
) -> Game:
    """设置游戏的定时下架/上架时间。

    作用：更新 scheduled_take_down_at 与 scheduled_publish_at 并记审计。
    场景：PATCH /admin/games/{id}/schedule 路由；scheduler 到期扫描执行。
    参数：db - 数据库会话；admin - 操作者；game_id - 游戏 ID；
        scheduled_take_down_at/scheduled_publish_at - 计划时间（None 清除）。
    返回：刷新后的 Game；不存在时抛 AppError。
    """
    game = await db.get(Game, game_id)
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在")
    game.scheduled_take_down_at = scheduled_take_down_at
    game.scheduled_publish_at = scheduled_publish_at
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="schedule_game",
            target=str(game_id),
            detail={
                "scheduled_take_down_at": scheduled_take_down_at.isoformat()
                if scheduled_take_down_at
                else None,
                "scheduled_publish_at": scheduled_publish_at.isoformat()
                if scheduled_publish_at
                else None,
            },
        )
    )
    await db.commit()
    await db.refresh(game)
    return game


async def patch_game_featured(
    db: AsyncSession,
    admin: User,
    game_id: uuid.UUID,
    featured_rank: int | None,
) -> Game:
    """设置或取消游戏的精选排序位。

    作用：更新 featured_rank（None 表示取消精选）并记审计。
    场景：PATCH /admin/games/{id}/featured 路由调用。
    参数：db - 数据库会话；admin - 操作者；game_id - 游戏 ID；featured_rank - 排序值或 None。
    返回：刷新后的 Game；非 published 或不存在时抛 AppError。
    """
    game = await db.get(Game, game_id)
    if game is None:
        raise AppError(ErrorCode.GAME_NOT_FOUND, "游戏不存在")
    if game.status != GameStatus.PUBLISHED.value:
        raise AppError(ErrorCode.INVALID_STATE, "仅已发布游戏可设为精选")
    game.featured_rank = featured_rank
    db.add(
        AuditLog(
            actor_id=admin.id,
            action="feature_game",
            target=str(game_id),
            detail={"featured_rank": featured_rank},
        )
    )
    await db.commit()
    await db.refresh(game)
    return game
