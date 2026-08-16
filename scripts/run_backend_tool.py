"""在 backend/ 目录下运行 mypy/bandit，并去掉路径前缀 backend/。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_BACKEND = _ROOT / "backend"


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: run_backend_tool.py <tool> [args...] [files...]", file=sys.stderr)
        return 2

    tool, *rest = argv[1:]
    tool_args: list[str] = []
    files: list[str] = []
    for item in rest:
        path = Path(item)
        if path.suffix == ".py" or path.as_posix().startswith("backend/"):
            parts = path.as_posix().split("/")
            if parts and parts[0] == "backend":
                files.append("/".join(parts[1:]))
            else:
                files.append(path.as_posix())
        else:
            tool_args.append(item)

    if not files:
        return 0

    cmd = ["uv", "run", tool, *tool_args, *files]
    return subprocess.call(cmd, cwd=_BACKEND)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
