"""平台侧 Vite+TS 固定模板加载（P1 验证用，§27 P1）。"""

from pathlib import Path

_SKIP_DIRS = {"node_modules", "dist", ".pnpm-store"}
_SKIP_FILES = {"pnpm-lock.yaml", "README.md"}


def repo_root() -> Path:
    """定位 monorepo 仓库根目录。

    场景：解析 docker/templates 等跨包资源路径。
    返回：仓库根 Path（``backend/app/forge/build/template.py`` 上溯 4 级）。
    """
    return Path(__file__).resolve().parents[4]


def vite_ts_template_dir() -> Path:
    """返回平台 Vite+TS 固定模板目录。

    场景：P1 构建链加载脚手架、生成 vite.config 回退。
    返回：``docker/templates/vite-ts`` 的绝对路径。
    """
    return repo_root() / "docker" / "templates" / "vite-ts"


def load_vite_ts_template_files() -> dict[str, str]:
    """加载 P1 固定 Vite+TS 模板文件集。

    场景：demo 构建、manifest 生成；跳过 lockfile 与构建产物。
    返回：``{相对路径: 文件文本}``；目录缺失时抛 FileNotFoundError。
    """
    root = vite_ts_template_dir()
    if not root.is_dir():
        msg = f"Vite+TS 模板目录不存在: {root}"
        raise FileNotFoundError(msg)

    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.name in _SKIP_FILES:
            continue
        files[rel] = path.read_text(encoding="utf-8")
    return files
