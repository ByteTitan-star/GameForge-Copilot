"""把本地缓存（HOSTING_ROOT/{game_id}/{version}/）的现有产物回填到对象存储。

用途：把 HOSTING_BACKEND 从 local 切到 s3 之前生成、只存在本地的历史产物，
批量上传到 OSS，让本地缓存丢失/换机器后仍可试玩。走项目真实 S3HostingBackend
代码路径（复用 checksum 配置与 key 规则），不绕过。

后续新生成的产物会由 forge/generate 链路自动写 OSS（store.write_* → S3 后端），
本脚本只处理「切换 backend 之前的历史产物」这一次性回填。

用法（在 backend/ 目录）：
    uv run python -m scripts.backfill_oss              # 实际回填
    uv run python -m scripts.backfill_oss --dry-run    # 只列待上传，不写

前置：backend/.env 已 HOSTING_BACKEND=s3 且 S3_* 配置正确（先用 verify_oss 自检）。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# 版本目录名是纯数字；game_id 是 UUID 形态。用这两个特征区分，避免误扫非产物目录。


def _scan_local_artifacts(root: Path) -> list[tuple[uuid.UUID, int, Path]]:
    """扫描本地缓存根，返回 [(game_id, version, version_dir), ...]。

    只收集 含 index.html 的版本目录（与 write_artifact 契约一致：产物必有 index.html）。
    """
    if not root.is_dir():
        return []
    found: list[tuple[uuid.UUID, int, Path]] = []
    for game_dir in root.iterdir():
        if not game_dir.is_dir():
            continue
        try:
            game_id = uuid.UUID(game_dir.name)
        except ValueError:
            continue  # 非 UUID 目录名（如自检残留或缓存污染），跳过
        for ver_dir in game_dir.iterdir():
            if not ver_dir.is_dir() or not ver_dir.name.isdigit():
                continue
            if not (ver_dir / "index.html").exists():
                continue
            found.append((game_id, int(ver_dir.name), ver_dir))
    return found


async def _backfill_one(
    backend: object,
    game_id: uuid.UUID,
    version: int,
    ver_dir: Path,
    dry_run: bool,
) -> tuple[int, int]:
    """回填单个版本目录，返回 (文件数, 字节数)。跳过自检标记文件。"""
    files = sorted(p for p in ver_dir.rglob("*") if p.is_file())
    n_files = 0
    n_bytes = 0
    for f in files:
        rel = f.relative_to(ver_dir).as_posix()
        data = f.read_bytes()
        if dry_run:
            n_files += 1
            n_bytes += len(data)
            continue
        # 走真实 write_bytes：上传 OSS + 同步刷新本地 cache（幂等，重复跑安全）
        await backend.write_bytes(game_id, version, rel, data)
        n_files += 1
        n_bytes += len(data)
    return n_files, n_bytes


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="回填本地缓存产物到对象存储")
    parser.add_argument("--dry-run", action="store_true", help="只列待上传，不写 OSS")
    args = parser.parse_args(argv)

    from app.core.config import settings
    from app.core.errors import AppError
    from app.hosting.factory import get_hosting_backend

    if settings.hosting_backend != "s3":
        print(f"[FAIL] HOSTING_BACKEND={settings.hosting_backend!r}，需为 's3'。")
        print("       （回填只对 S3 后端有意义；local 后端产物不会进 OSS）")
        return 2

    root = Path(settings.hosting_root)
    if not root.is_absolute():
        # 后端本地 cache 默认相对 backend/ 工作目录；脚本也在 backend/ 跑，保持一致
        root = Path(__file__).resolve().parent.parent / settings.hosting_root
    artifacts = _scan_local_artifacts(root)
    if not artifacts:
        print(f"[noop] 本地缓存 {root} 下没有可回填的产物目录。")
        return 0

    print(f"扫描到 {len(artifacts)} 个版本产物待回填（dry_run={args.dry_run}）：")
    total_files = 0
    total_bytes = 0
    try:
        backend = get_hosting_backend()
    except AppError as e:
        print(f"[FAIL] 托管后端构造失败: {e.message}")
        return 1

    for game_id, version, ver_dir in artifacts:
        try:
            n, sz = await _backfill_one(backend, game_id, version, ver_dir, args.dry_run)
        except AppError as e:
            print(f"  [FAIL] {game_id} v{version}: {e.message}")
            return 1
        total_files += n
        total_bytes += sz
        verb = "将上传" if args.dry_run else "已上传"
        print(f"  {game_id} v{version}: {verb} {n} 个文件 / {sz} 字节")

    unit = "KB"
    size_disp = f"{total_bytes / 1024:.1f} {unit}"
    if args.dry_run:
        print(
            f"\n[dry-run] 回填预览完成：共 {total_files} 个文件 / {size_disp}。"
            "去掉 --dry-run 实际执行。"
        )
    else:
        print(
            f"\n[done] 回填完成：{len(artifacts)} 个版本 / {total_files} 个文件"
            f" / {size_disp} 已上传到 OSS。"
        )
        print("       可用 `uv run python -m scripts.verify_oss` 不适用（它只测连通）；")
        print("       直接 list OSS 前缀或在后端起来后试玩验证。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
