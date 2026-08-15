"""固定 demo 路由与源码测试。"""

from app.forge.build.demos import (
    PHASER_MATTER_DEMO_ROUTING,
    PHASER_MATTER_DEMO_SOURCE,
    REACT_DEMO_ROUTING,
    REACT_DEMO_SOURCE,
)
from app.forge.build.manifest import generate_package_json, merge_workspace
from app.forge.build.routing import validate_routing


def test_react_demo_routing_valid() -> None:
    assert validate_routing(REACT_DEMO_ROUTING) == []
    pkg = generate_package_json(REACT_DEMO_ROUTING)
    assert "react" in pkg
    assert "@vitejs/plugin-react" in pkg


def test_phaser_matter_demo_routing_valid() -> None:
    assert validate_routing(PHASER_MATTER_DEMO_ROUTING) == []
    pkg = generate_package_json(PHASER_MATTER_DEMO_ROUTING)
    assert "phaser" in pkg
    assert "matter-js" in pkg


def test_demos_merge_workspace_has_entries() -> None:
    ws = merge_workspace(REACT_DEMO_ROUTING, REACT_DEMO_SOURCE)
    assert "src/main.tsx" in ws
    assert "package.json" in ws
    assert "./" in ws["vite.config.ts"]
    ws2 = merge_workspace(PHASER_MATTER_DEMO_ROUTING, PHASER_MATTER_DEMO_SOURCE)
    assert "src/main.ts" in ws2
    assert "index.html" in ws2
