"""沙箱抽象：execute_code 接口。M5 本地后端，M6 docker 后端。"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class BuildResult:
    ok: bool
    files: dict[str, bytes] = field(default_factory=dict)
    logs: str = ""
    error: str | None = None


class Sandbox(Protocol):
    """把源码（+可选构建命令）在受限环境跑出静态产物。"""

    async def execute(
        self,
        source: dict[str, str],
        build_cmd: Sequence[str] | None = None,
        *,
        collect_root: str = ".",
    ) -> BuildResult: ...
