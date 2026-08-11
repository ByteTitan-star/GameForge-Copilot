"""创建或提权管理员账号（运维专用）。

打破「没有 admin 就建不了 admin」的死锁：本脚本绕过注册接口，直接在数据库
写入一个 role=admin 的新用户，或把已有用户提权为管理员。仅限运维使用，不暴露给普通用户。

用法：
    cd backend && uv run python -m scripts.create_admin --email admin@example.com
    cd backend && uv run python -m scripts.create_admin --email a@b.com --password 'secret123'
    # 邮箱已存在时必须显式 --promote-existing，否则报错退出（防误操作）
    cd backend && uv run python -m scripts.create_admin --email a@b.com --promote-existing
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.core import db
from app.enums import Role
from app.models.user import User

MIN_PASSWORD_LEN = 8


def _validate_password(pw: str) -> None:
    if len(pw) < MIN_PASSWORD_LEN:
        print(f"错误：密码至少 {MIN_PASSWORD_LEN} 位。", file=sys.stderr)
        sys.exit(2)


def _prompt_password() -> str:
    pw = getpass.getpass(f"管理员密码（至少 {MIN_PASSWORD_LEN} 位）: ")
    _validate_password(pw)
    if pw != getpass.getpass("再次输入以确认: "):
        print("错误：两次输入不一致。", file=sys.stderr)
        sys.exit(2)
    return pw


async def _create_or_promote(
    session: AsyncSession, email: str, password: str | None, promote: bool
) -> None:
    user = await session.scalar(select(User).where(User.email == email))

    if user is None:
        # 新建管理员：必须有密码
        if password is None:
            password = _prompt_password()
        else:
            _validate_password(password)
        user = User(
            email=email,
            password_hash=hash_password(password),
            role=Role.ADMIN.value,
            email_verified=True,
            disabled=False,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"✓ 已创建管理员账号：{user.email}（id={user.id}）")
        return

    # 邮箱已存在：未带 --promote-existing 则拒绝，避免误把普通用户提权
    if not promote:
        print(
            f"错误：邮箱 {email} 已存在（当前 role={user.role}）。\n"
            "如需提权为管理员，请加 --promote-existing 重新运行。",
            file=sys.stderr,
        )
        sys.exit(2)

    changed: list[str] = []
    if user.role != Role.ADMIN.value:
        user.role = Role.ADMIN.value
        changed.append("role→admin")
    if not user.email_verified:
        user.email_verified = True
        changed.append("email_verified→true")
    if user.disabled:
        user.disabled = False
        changed.append("disabled→false")
    if password is not None:
        _validate_password(password)
        user.password_hash = hash_password(password)
        changed.append("password→updated")

    if not changed:
        print(f"无需改动：{email} 已是可用管理员（role=admin、已验证、未禁用）。")
        return
    await session.commit()
    print(f"✓ 已提权现有账号为管理员：{user.email}（id={user.id}），变更：{', '.join(changed)}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="创建或提权管理员账号（运维专用）。")
    parser.add_argument("--email", required=True, help="管理员邮箱")
    parser.add_argument(
        "--password",
        default=None,
        help="管理员密码；省略则在新建时交互输入（提权时省略表示不改密码）",
    )
    parser.add_argument(
        "--promote-existing",
        action="store_true",
        help="邮箱已存在时允许提权为管理员；不指定则遇到已存在邮箱直接报错退出",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    email = args.email.strip()
    async with db.SessionLocal() as session:
        await _create_or_promote(session, email, args.password, args.promote_existing)


if __name__ == "__main__":
    asyncio.run(main())
