"""生成方法论 skill 文本（docs/03）；非玩法硬编码。"""

from pathlib import Path

_DIR = Path(__file__).parent


def load_skill(name: str) -> str:
    path = _DIR / name
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
