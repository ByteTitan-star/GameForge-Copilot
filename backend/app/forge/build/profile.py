"""Build Profile：builder / catalog / template 三版本独立演进（§8）。"""

import json
from dataclasses import asdict, dataclass
from typing import Self


@dataclass(frozen=True)
class BuildProfile:
    """构建链三版本指纹：builder / catalog / template 独立演进。"""

    builder_version: str = "v1"
    dependency_catalog_version: str = "2026-08-14.1"
    template_version: str = "v1"

    def to_json(self) -> str:
        """序列化为 build-profile.json 内容。

        返回：带缩进的 JSON 字符串。
        """
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> Self:
        """从 build-profile.json 反序列化。

        参数：raw — JSON 文本。
        返回：BuildProfile 实例。
        """
        data = json.loads(raw)
        return cls(
            builder_version=str(data["builder_version"]),
            dependency_catalog_version=str(data["dependency_catalog_version"]),
            template_version=str(data["template_version"]),
        )


def default_build_profile() -> BuildProfile:
    """返回默认 BuildProfile（三版本字段均为默认值）。

    场景：BuildPipeline、manifest 未指定 profile 时。
    参数：无。
    返回：BuildProfile 实例。
    """
    return BuildProfile()
