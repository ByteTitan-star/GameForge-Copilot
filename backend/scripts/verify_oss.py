"""OSS 托管连通性自检脚本。

走项目真实代码路径（S3HostingBackend + settings 读 .env），真实连一次阿里云 OSS：
write_bytes → read_bytes → list_files → 清理。验证凭证 / endpoint / region /
addressing_style 是否能让项目的托管链路真正跑通。

用法（在 backend/ 目录）：
    uv run python -m scripts.verify_oss

前置：backend/.env 里
    HOSTING_BACKEND=s3
    S3_ENDPOINT / S3_REGION / S3_BUCKET / S3_AK / S3_SK / S3_PREFIX / S3_ADDRESSING_STYLE
均已正确配置（见 docs 或 .env.example 注释）。

注意：脚本会在 bucket 的 S3_PREFIX 下写入两个测试对象，测完即删，不留垃圾。
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# 固定测试上下文：version 用大数避免与真实产物版本撞 key；game_id 用固定 UUID 便于人工排查残留。
_TEST_GAME_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")
_TEST_VERSION = 999_999
_README_REL = "README.md"
_MARKER_REL = "_oss_selftest.md"


async def _delete_test_objects(backend: object, game_id: uuid.UUID, version: int) -> None:
    """清理本次写入的测试对象。直接复用 backend 的 boto3 client（Config/style/checksum 都对）。"""
    from app.core.config import settings

    client = backend._client  # type: ignore[attr-defined]  # S3HostingBackend 内部已配好 style
    prefix = f"{settings.s3_prefix.strip('/')}/{game_id}/{version}/"
    resp = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
    objs = resp.get("Contents", []) or []
    # 逐个删除：OSS 对批量 delete_objects 的 XML 体兼容性差（MissingArgument），
    # 单对象 delete_object 各家 S3 兼容实现都稳定。
    for o in objs:
        client.delete_object(Bucket=settings.s3_bucket, Key=o["Key"])
    # 同步清本地 cache（write_bytes 会写一份本地缓存）
    from app.hosting import local as local_store

    for rel in (_README_REL, _MARKER_REL, "index.html"):
        cache = local_store.index_path(game_id, version)
        if cache is not None:
            target = cache.parent / rel
            if target.exists():
                target.unlink()


async def main() -> int:
    from app.core.config import settings
    from app.core.errors import AppError
    from app.hosting.factory import get_hosting_backend

    # 0. 前置校验：必须切到 s3
    if settings.hosting_backend != "s3":
        print(f"[FAIL] HOSTING_BACKEND={settings.hosting_backend!r}，需设为 's3' 才能测 OSS。")
        print("       （HOSTING_ROOT 是本地缓存目录，不是后端开关；开关是 HOSTING_BACKEND）")
        return 2

    print("[1/6] 配置概览：")
    print(f"        endpoint  = {settings.s3_endpoint}")
    print(f"        region    = {settings.s3_region}")
    print(f"        bucket    = {settings.s3_bucket}")
    print(f"        prefix    = {settings.s3_prefix}")
    print(f"        style     = {settings.s3_addressing_style}")
    missing = [
        n
        for n, v in (
            ("S3_ENDPOINT", settings.s3_endpoint),
            ("S3_REGION", settings.s3_region),
            ("S3_BUCKET", settings.s3_bucket),
            ("S3_AK", settings.s3_ak),
            ("S3_SK", settings.s3_sk),
        )
        if not v
    ]
    if missing:
        print(f"[FAIL] 缺少必填配置: {', '.join(missing)}")
        return 2

    # endpoint 含 -internal 且本机不在阿里云内网时给个提示（不阻断，让真实错误说话）
    if "internal" in settings.s3_endpoint:
        print(
            "        ⚠️  endpoint 含 -internal：本机/非阿里云内网环境连不上，建议改公网 endpoint。"
        )

    # 构造后端（走项目真实代码；构造失败通常是 addressing_style / 凭证问题）
    try:
        backend = get_hosting_backend()
        # 触发 S3HostingBackend.__init__ 实际建连校验
        _ = backend.__class__.__name__
    except AppError as e:
        print(f"[FAIL] 托管后端构造失败: {e.message}")
        return 1

    # 读项目根 README.md 作为上传内容（证明真实文件可上传）
    repo_root = Path(__file__).resolve().parents[2]
    readme = repo_root / "README.md"
    if not readme.exists():
        print(f"[FAIL] 找不到 {readme}，无法作为测试上传内容。")
        return 1
    readme_bytes = readme.read_bytes()

    marker = (
        b"OSS selftest marker\n"
        b"uploaded by scripts/verify_oss.py via project S3HostingBackend.\n"
        + f"game_id={_TEST_GAME_ID} version={_TEST_VERSION}\n".encode()
        + b"status=tested-ok\n"
    )

    print("[2/6] write_bytes: 上传 README.md + 自检标记 ...")
    try:
        await backend.write_bytes(_TEST_GAME_ID, _TEST_VERSION, _README_REL, readme_bytes)
        await backend.write_bytes(_TEST_GAME_ID, _TEST_VERSION, _MARKER_REL, marker)
    except AppError as e:
        print(f"[FAIL] 上传失败: {e.message}")
        print(
            "       常见原因：AK 缺 PutObject 权限 / "
            "addressing_style 应为 virtual / endpoint 用了 -internal"
        )
        return 1

    print("[3/6] read_bytes: 回读 README.md 并比对内容 ...")
    got = await backend.read_bytes(_TEST_GAME_ID, _TEST_VERSION, _README_REL)
    if got != readme_bytes:
        print(
            f"[FAIL] 回读内容与原文不一致（len 期望 {len(readme_bytes)}，实际 {len(got or b'')}）"
        )
        await _delete_test_objects(backend, _TEST_GAME_ID, _TEST_VERSION)
        return 1

    print("[4/6] list_files: 列举该版本产物 ...")
    files = await backend.list_files(_TEST_GAME_ID, _TEST_VERSION)
    names = {f.path for f in files}
    if _README_REL not in names or _MARKER_REL not in names:
        print(f"[FAIL] list_files 未返回测试对象，实际: {sorted(names)}")
        await _delete_test_objects(backend, _TEST_GAME_ID, _TEST_VERSION)
        return 1
    print(f"        列到 {len(files)} 个对象: {sorted(names)}")

    print("[5/6] 清理测试对象 ...")
    await _delete_test_objects(backend, _TEST_GAME_ID, _TEST_VERSION)

    print("[6/6] ✅ OSS 托管链路自检通过：write/read/list 均成功，测试对象已清理。")
    print("       项目 S3HostingBackend 可直接用于 forge 产物托管。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
