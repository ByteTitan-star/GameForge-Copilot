"""Build Profile：builder / catalog / template 三版本独立演进（§8）。"""

import json
from dataclasses import asdict, dataclass
from typing import Self


@dataclass(frozen=True)
class BuildProfile:
    builder_version: str = "v1"
    dependency_catalog_version: str = "2026-08-14.1"
    template_version: str = "v1"

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> Self:
        data = json.loads(raw)
        return cls(
            builder_version=str(data["builder_version"]),
            dependency_catalog_version=str(data["dependency_catalog_version"]),
            template_version=str(data["template_version"]),
        )


def default_build_profile() -> BuildProfile:
    return BuildProfile()
