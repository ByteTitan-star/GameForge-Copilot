"""P1 构建链自检：固定 Vite+TS 模板走完 prepare → offline build → dist/。

用法（在 backend/ 目录）：
    # Docker builder（推荐，需 gameforge-builder:v1 镜像）
    BUILDER_BACKEND=docker RUN_BUILD_PIPELINE=1 uv run python -m scripts.verify_build_pipeline

    # 本地 pnpm fallback（§24，需 pnpm 11+ 与 Node）
    BUILDER_BACKEND=local RUN_BUILD_PIPELINE=local uv run python -m scripts.verify_build_pipeline

对应 docs/build-pipeline.md §26 验证点 1–5。
"""

from __future__ import annotations

import asyncio
import sys

from app.core.config import settings
from app.forge.build import BuildPipeline


def _check_pnpm_version() -> None:
    import shutil
    import subprocess

    if shutil.which("corepack"):
        out = subprocess.check_output(
            ["corepack", "pnpm", "-v"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
    else:
        pnpm = shutil.which("pnpm")
        if not pnpm:
            print("ERROR: 未找到 corepack/pnpm，请安装 Node 20+ 或使用 BUILDER_BACKEND=docker")
            sys.exit(1)
        out = subprocess.check_output([pnpm, "-v"], text=True).strip()
    major = int(out.split(".", maxsplit=1)[0])
    if major < 11:
        print(
            f"WARN: 当前 pnpm {out}，构建链硬约束④要求 pnpm 11 allowBuilds；"
            "模板 packageManager 会经 corepack 激活 11.21.0"
        )
    else:
        print(f"pnpm {out}")


async def _run() -> int:
    mode = settings.builder_backend
    print(f"builder_backend={mode} builder_image={settings.builder_image}")
    print(f"pnpm_store={settings.pnpm_store_path} registry={settings.npm_registry}")

    if mode == "local":
        _check_pnpm_version()

    result = await BuildPipeline().run_vite_ts_demo()
    if not result.ok:
        print("FAIL:", result.error or "unknown")
        if result.logs:
            print("--- logs (tail) ---")
            tail = result.logs[-4000:]
            sys.stdout.buffer.write(tail.encode("utf-8", errors="replace") + b"\n")
        return 1

    print("OK: dist/index.html 已生成")
    print(f"dist files: {sorted(result.dist)}")
    if result.build_snapshot:
        print(f"build snapshot: {sorted(result.build_snapshot)}")
    if result.prepare and result.prepare.skipped:
        print("prepare: cache hit")

    html = result.dist.get("index.html", b"").decode("utf-8", errors="replace")
    if "./assets/" not in html and 'src="./assets/' not in html:
        print("WARN: index.html 未检测到相对 assets 路径（硬约束③ base:'./'）")
    else:
        print("OK: dist 资源为相对路径")

    asset_js = next((k for k in result.dist if k.startswith("assets/") and k.endswith(".js")), None)
    if asset_js:
        print(f"OK: {asset_js} ({len(result.dist[asset_js])} bytes)")

    if "pnpm-lock.yaml" not in result.build_snapshot:
        print("WARN: build snapshot 缺少 pnpm-lock.yaml")
    else:
        print("OK: pnpm-lock.yaml 已保存")

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
