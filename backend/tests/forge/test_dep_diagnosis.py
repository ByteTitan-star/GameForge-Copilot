"""构建日志依赖诊断（#161）：module-not-found → 结构化 JSON 修复提示。"""

from __future__ import annotations

import json

from app.forge.build.dep_diagnosis import (
    dependency_hint_block,
    diagnose_dependency_failure,
    enrich_build_error,
)

# 贴近 vite/tsc 真实输出形态的日志样本
_VITE_LOGS = """error: Could not resolve 'howler'
    at file /workspace/src/main.ts:2:22:
15:29:26 [vite] error while parsing /workspace/src/main.ts:
error during build: Could not resolve './style.css' from "src/main.ts"
x Build failed in 3.42s"""

_TSC_LOGS = (
    "src/main.ts:1:24 - error TS2307: Cannot find module 'three' "
    "or its corresponding type declarations.\n"
    "1 import * as THREE from 'three';\n"
    "src/ui.ts:2:1 - error TS2307: Cannot find module '@tweenjs/tween.js' "
    "or its corresponding type declarations.\n"
    "Found 2 errors."
)


def test_vite_could_not_resolve_in_catalog() -> None:
    out = diagnose_dependency_failure(_VITE_LOGS)
    # './style.css' 是相对路径，不算缺包；howler 在 catalog
    assert [f["package"] for f in out] == ["howler"]
    assert out[0]["kind"] == "undeclared_or_unresolved_dependency"
    assert out[0]["in_catalog"] is True
    assert "add 'howler' to the dependencies" in out[0]["action"]
    assert "Could not resolve 'howler'" in out[0]["evidence"]


def test_tsc_cannot_find_module_out_of_catalog() -> None:
    out = diagnose_dependency_failure(_TSC_LOGS)
    assert {f["package"] for f in out} == {"three", "@tweenjs/tween.js"}
    for f in out:
        assert f["in_catalog"] is False
        assert "NOT in the platform catalog" in f["action"]
        assert "rewrite the code" in f["action"]


def test_same_package_reported_once() -> None:
    logs = "\n".join(
        [
            "error: Could not resolve 'three'",
            "error: Could not resolve 'three'",
            'error TS2307: Cannot find module \'three\'',
        ]
    )
    assert len(diagnose_dependency_failure(logs)) == 1


def test_no_match_returns_empty_and_keeps_logs() -> None:
    logs = "internal server error\npnpm: ERR_PNPM_META_FETCH_FAIL"
    assert diagnose_dependency_failure(logs) == []
    assert enrich_build_error(logs) == logs


def test_hint_block_is_valid_json_with_header() -> None:
    block = dependency_hint_block(_VITE_LOGS)
    assert block.startswith("【依赖诊断")
    payload = json.loads(block.split("】\n", 1)[1])
    assert payload[0]["package"] == "howler"


def test_enrich_prepends_hint_and_keeps_raw_logs() -> None:
    enriched = enrich_build_error(_TSC_LOGS)
    assert enriched.startswith("【依赖诊断")
    assert "TS2307" in enriched  # 原始日志完整保留在后
    assert enriched.index("【依赖诊断") < enriched.index("TS2307")


def test_findings_capped() -> None:
    logs = "\n".join(f"error: Could not resolve 'pkg{i}'" for i in range(10))
    assert len(diagnose_dependency_failure(logs)) == 6
