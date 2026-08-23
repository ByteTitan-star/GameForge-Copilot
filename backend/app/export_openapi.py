"""导出 FastAPI 生成的 OpenAPI 快照到文件或 stdout。

推荐写文件（强制 UTF-8 / LF，避免 shell `>` 重定向在 Windows 上把中文写成 cp936 损坏）：

    uv run python -m app.export_openapi contracts/openapi.json

或打印到 stdout（UTF-8 字节，直写 stdout.buffer 绕开 Windows 文本模式编码）：

    uv run python -m app.export_openapi
"""

import json
import sys
from pathlib import Path

from app.main import app


def export() -> str:
    """序列化当前 FastAPI 应用的 OpenAPI 规范。

    作用：生成带缩进、保留中文的 OpenAPI JSON 字符串。
    场景：CLI 导出契约文件或打印到 stdout 时调用。
    参数：无。
    返回：以换行符结尾的 OpenAPI JSON 文本。
    """
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    out = export()
    if len(sys.argv) > 1:
        # 写文件：显式 UTF-8 + LF，不依赖 shell 重定向的编码行为
        Path(sys.argv[1]).write_text(out, encoding="utf-8", newline="\n")
    else:
        # stdout：用 buffer 写 UTF-8 字节，绕开 Windows 默认文本编码
        sys.stdout.buffer.write(out.encode("utf-8"))
