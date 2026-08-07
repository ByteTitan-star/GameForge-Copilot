"""导出 FastAPI 生成的 OpenAPI 快照到 stdout。

用法：`uv run python -m app.export_openapi > contracts/openapi.json`
"""

import json

from app.main import app


def export() -> str:
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    print(export(), end="")
