"""manifest JSON 解析测试。"""

import json

from app.forge.build.manifest import _loads_json_object, generate_tsconfig
from app.forge.build.routing import BuildRouting


def test_loads_json_object_strips_comments() -> None:
    raw = '// comment\n{\n  "compilerOptions": {"strict": true}\n}\n'
    data = _loads_json_object(raw)
    assert data["compilerOptions"]["strict"] is True


def test_generate_tsconfig_from_template() -> None:
    routing = BuildRouting(build="vite", renderer="phaser3")
    out = generate_tsconfig(routing)
    data = json.loads(out)
    assert data["compilerOptions"]["strict"] is True


def test_generate_tsconfig_react_jsx() -> None:
    routing = BuildRouting(build="vite", renderer="canvas", ui="react")
    data = json.loads(generate_tsconfig(routing))
    assert data["compilerOptions"]["jsx"] == "react-jsx"
