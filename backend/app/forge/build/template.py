"""平台侧 Vite+TS 固定模板加载（P1 验证用，§27 P1）。"""

from pathlib import Path

_SKIP_DIRS = {"node_modules", "dist", ".pnpm-store"}
_SKIP_FILES = {"pnpm-lock.yaml", "README.md"}


def repo_root() -> Path:
    # backend/app/forge/build/template.py → parents[4] = 仓库根
    return Path(__file__).resolve().parents[4]


def vite_ts_template_dir() -> Path:
    return repo_root() / "docker" / "templates" / "vite-ts"


def load_vite_ts_template_files() -> dict[str, str]:
    """加载 P1 固定模板（不含 lockfile / 构建产物）。"""
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
