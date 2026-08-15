"""清理 OSS 中不对应任何 DB 游戏的孤儿/测试产物对象。

背景：conftest 曾未强制 hosting_backend=local，.env 切到 s3 后跑 pytest 会把
测试产物（含 60MB 配额用例、13 字节假 index.html/thumb.png）泄进真实 OSS。
本脚本按「对象 key 的 game_id 段不在 games 表」判定垃圾，逐个删除。

用法（在 backend/ 目录）：
    uv run python -m scripts.prune_oss_orphans --dry-run   # 只列将删除的对象
    uv run python -m scripts.prune_oss_orphans             # 实际删除

注意：只清 gameforge 前缀下符合 {prefix}/{game_id}/{version}/... 结构的对象；
official 游戏（固定 UUID 00000000-...-0a1/a2/a3）在 games 表中，不会被删。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# backend/ 目录（脚本上一层）
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _parse_game_id(key: str, prefix: str) -> uuid.UUID | None:
    """从对象 key 提取 game_id：{prefix}/{game_id}/{version}/{rel...}。"""
    head = prefix.strip("/")
    parts = key.split("/")
    if head:
        if not key.startswith(head + "/"):
            return None
        parts = parts[1:]
    if not parts:
        return None
    try:
        return uuid.UUID(parts[0])
    except ValueError:
        return None


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="清理 OSS 孤儿/测试产物")
    parser.add_argument("--dry-run", action="store_true", help="只列将删除的对象，不执行")
    parser.add_argument(
        "--keep-ids",
        default="",
        help="逗号分隔的 game_id 清单；提供时跳过 DB 查询直接用此清单（DB 不可用时用）",
    )
    args = parser.parse_args(argv)

    from app.core.config import settings

    if settings.hosting_backend != "s3":
        print(f"[FAIL] HOSTING_BACKEND={settings.hosting_backend!r}，需为 's3'。")
        return 2

    # DB 全部 game_id（含 official 固定 UUID）；DB 不可用时用 --keep-ids 显式给定
    if args.keep_ids:
        db_ids = {s.strip() for s in args.keep_ids.split(",") if s.strip()}
        print(f"使用显式 keep 清单: {len(db_ids)} 个 game_id（未查 DB）")
    else:
        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.models.game import Game

        async with SessionLocal() as db:
            db_ids = {str(g.id) for g in (await db.scalars(select(Game))).all()}
        print(f"DB 中游戏数: {len(db_ids)}（其产物将被保留）")

    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint.rstrip("/"),
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_ak,
        aws_secret_access_key=settings.s3_sk,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": settings.s3_addressing_style},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )
    prefix = settings.s3_prefix.strip("/")

    # 分页列出全部对象
    objs: list[dict] = []
    token: str | None = None
    while True:
        kw: dict[str, object] = {"Bucket": settings.s3_bucket, "Prefix": prefix}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        objs += resp.get("Contents", []) or []
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    print(f"OSS {prefix}/ 下对象总数: {len(objs)}")

    # 分类：保留(DB 有) / 删除(DB 无)
    keep, drop = [], []
    for o in objs:
        gid = _parse_game_id(o["Key"], prefix)
        if gid is not None and str(gid) in db_ids:
            keep.append(o)
        else:
            drop.append(o)
    keep_bytes = sum(o["Size"] for o in keep)
    drop_bytes = sum(o["Size"] for o in drop)
    print(f"保留: {len(keep)} 个对象 / {keep_bytes / 1024 / 1024:.2f} MB（DB 游戏产物）")
    print(f"待删: {len(drop)} 个对象 / {drop_bytes / 1024 / 1024:.2f} MB（孤儿/测试垃圾）")
    if drop:
        print()
        print("待删对象预览（按大小排序，最多列 20 个）:")
        for o in sorted(drop, key=lambda x: -x["Size"])[:20]:
            print(f"  {o['Size']:>12,} 字节  {o['Key']}")
        if len(drop) > 20:
            print(f"  ... 其余 {len(drop) - 20} 个略")

    if args.dry_run:
        print("\n[dry-run] 未删除任何对象。去掉 --dry-run 实际执行。")
        return 0

    if not drop:
        print("\n[done] 无需清理。")
        return 0

    # 逐个删除：OSS 对批量 delete_objects 的 XML 兼容性差，单删稳定
    for i, o in enumerate(drop, 1):
        client.delete_object(Bucket=settings.s3_bucket, Key=o["Key"])
        if i % 50 == 0 or i == len(drop):
            print(f"  已删除 {i}/{len(drop)}")
    print(f"\n[done] 已删除 {len(drop)} 个对象（释放 {drop_bytes / 1024 / 1024:.2f} MB）。")
    print(f"OSS 剩余 {len(keep)} 个对象，均为 DB 游戏产物。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
