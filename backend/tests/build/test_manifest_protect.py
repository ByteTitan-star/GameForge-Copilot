"""ADR-07 P0-2: protect platform manifest from LLM source_files overrides."""

from app.forge.build.manifest import generate_manifest_files, merge_workspace
from app.forge.build.routing import BuildRouting
from app.sandbox.builder import sanitize_package_manager_version


def test_merge_workspace_ignores_protected_overrides() -> None:
    routing = BuildRouting(build="vite", renderer="canvas")
    base = generate_manifest_files(routing)
    poisoned = {
        "package.json": '{"name":"evil"}',
        "pnpm-workspace.yaml": "packages:\n  - evil\n",
        "vite.config.ts": "export default {}",
        "tsconfig.json": "{}",
        "src/main.ts": "console.log(1)",
    }
    ws = merge_workspace(routing, poisoned)
    assert ws["package.json"] == base["package.json"]
    assert ws["pnpm-workspace.yaml"] == base["pnpm-workspace.yaml"]
    assert ws["vite.config.ts"] == base["vite.config.ts"]
    assert ws["tsconfig.json"] == base["tsconfig.json"]
    assert ws["src/main.ts"] == "console.log(1)"


def test_sanitize_package_manager_version() -> None:
    assert sanitize_package_manager_version("pnpm@9.15.0") == "9.15.0"
    assert sanitize_package_manager_version("pnpm@11.21.0") == "11.21.0"
    assert sanitize_package_manager_version("pnpm@9.15.0; rm -rf /") is None
    assert sanitize_package_manager_version("yarn@1.0.0") is None
    assert sanitize_package_manager_version("") is None
