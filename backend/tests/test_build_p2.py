"""P2 模块单元测试：catalog / routing / manifest / code_output。"""

import json

from app.forge.build.catalog import DEPENDENCY_CATALOG, validate_catalog_packages
from app.forge.build.code_output import parse_code_output
from app.forge.build.manifest import generate_manifest_files, merge_workspace
from app.forge.build.routing import (
    BuildRouting,
    coerce_build_routing,
    resolve_package_versions,
    routing_from_design_doc,
    should_use_vite_pipeline,
    validate_routing,
)


def test_catalog_has_core_packages() -> None:
    for pkg in ("phaser", "vite", "typescript", "matter-js"):
        assert pkg in DEPENDENCY_CATALOG


def test_validate_catalog_packages_unknown() -> None:
    assert validate_catalog_packages(["matter-js", "evil-pkg"]) == ["evil-pkg"]


def test_coerce_build_routing_defaults() -> None:
    r = coerce_build_routing(None, engine_id="phaser3")
    assert r.build == "none"
    assert r.renderer == "phaser3"


def test_resolve_package_versions_auto_injects_renderer_and_tools() -> None:
    routing = BuildRouting(
        build="vite",
        renderer="phaser3",
        ui="none",
        dependencies=("matter-js",),
    )
    resolved = resolve_package_versions(routing)
    assert resolved["phaser"] == DEPENDENCY_CATALOG["phaser"]
    assert resolved["matter-js"] == DEPENDENCY_CATALOG["matter-js"]
    assert resolved["vite"] == DEPENDENCY_CATALOG["vite"]
    assert resolved["typescript"] == DEPENDENCY_CATALOG["typescript"]


def test_resolve_package_versions_react_ui() -> None:
    routing = BuildRouting(build="vite", renderer="canvas", ui="react", dependencies=())
    resolved = resolve_package_versions(routing)
    assert "react" in resolved
    assert "react-dom" in resolved
    assert "@vitejs/plugin-react" in resolved


def test_validate_routing_rejects_unknown_dependency() -> None:
    routing = BuildRouting(
        build="vite",
        renderer="canvas",
        dependencies=("not-a-real-package",),
    )
    errors = validate_routing(routing)
    assert any("未授权包" in e for e in errors)


def test_routing_from_design_doc() -> None:
    doc = {
        "engine": {"id": "phaser3"},
        "build_routing": {
            "build": "vite",
            "renderer": "phaser3",
            "ui": "none",
            "dependencies": ["howler"],
        },
    }
    routing = routing_from_design_doc(doc)
    assert routing.build == "vite"
    assert routing.dependencies == ("howler",)


def test_should_use_vite_pipeline() -> None:
    r = BuildRouting(build="vite", renderer="canvas")
    assert should_use_vite_pipeline(r, enabled=True)
    assert not should_use_vite_pipeline(r, enabled=False)
    assert not should_use_vite_pipeline(BuildRouting(build="none"), enabled=True)


def test_generate_manifest_files_contains_required() -> None:
    routing = BuildRouting(build="vite", renderer="phaser3", dependencies=("matter-js",))
    files = generate_manifest_files(routing)
    assert "package.json" in files
    assert "vite.config.ts" in files
    assert "pnpm-workspace.yaml" in files
    pkg = json.loads(files["package.json"])
    assert pkg["dependencies"]["phaser"] == DEPENDENCY_CATALOG["phaser"]
    assert pkg["dependencies"]["matter-js"] == DEPENDENCY_CATALOG["matter-js"]
    assert "./" in files["vite.config.ts"]


def test_generate_manifest_react_plugin_in_vite_config() -> None:
    routing = BuildRouting(build="vite", renderer="canvas", ui="react")
    config = generate_manifest_files(routing)["vite.config.ts"]
    assert "@vitejs/plugin-react" in config
    tsconfig = json.loads(generate_manifest_files(routing)["tsconfig.json"])
    assert tsconfig["compilerOptions"]["jsx"] == "react-jsx"


def test_merge_workspace_injects_index_html() -> None:
    routing = BuildRouting(build="vite", renderer="canvas")
    ws = merge_workspace(routing, {"src/main.ts": "console.log(1)"})
    assert "index.html" in ws
    assert "package.json" in ws
    assert ws["src/main.ts"] == "console.log(1)"


def test_parse_code_output_legacy_html() -> None:
    parsed = parse_code_output("<!DOCTYPE html><html></html>")
    assert parsed.format == "single-html"
    assert "index.html" in parsed.files


def test_parse_code_output_project_json() -> None:
    raw = json.dumps(
        {
            "format": "project",
            "build": "vite",
            "renderer": "phaser3",
            "ui": "none",
            "dependencies": ["matter-js"],
            "files": {"src/main.ts": "export {}"},
        }
    )
    parsed = parse_code_output(raw, default_engine="phaser3")
    assert parsed.format == "project"
    assert parsed.routing is not None
    assert parsed.routing.dependencies == ("matter-js",)
    assert parsed.errors == ()


def test_parse_code_output_project_unknown_dep_errors() -> None:
    raw = json.dumps(
        {
            "format": "project",
            "build": "vite",
            "renderer": "canvas",
            "ui": "none",
            "dependencies": ["evil"],
            "files": {"src/main.ts": "x"},
        }
    )
    parsed = parse_code_output(raw)
    assert parsed.errors
