"""§26 固定工程 demo 源码（不经过 LLM，验证 prepare → offline build → dist）。"""

from __future__ import annotations

from app.forge.build.routing import BuildRouting

REACT_DEMO_ROUTING = BuildRouting(
    build="vite",
    renderer="canvas",
    ui="react",
    dependencies=(),
)

PHASER_MATTER_DEMO_ROUTING = BuildRouting(
    build="vite",
    renderer="phaser3",
    ui="none",
    dependencies=("matter-js",),
)

REACT_DEMO_SOURCE: dict[str, str] = {
    "index.html": (
        '<!doctype html><html lang="zh-CN"><head>'
        '<meta charset="UTF-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        "<title>React Demo</title></head><body>"
        '<div id="root"></div>'
        '<script type="module" src="/src/main.tsx"></script>'
        "</body></html>"
    ),
    "src/main.tsx": (
        'import { createRoot } from "react-dom/client";\n'
        'import App from "./App";\n'
        'createRoot(document.getElementById("root")!).render(<App />);\n'
    ),
    "src/App.tsx": (
        "export default function App() {\n"
        '  return <h1 id="game-root">GameForge React Demo</h1>;\n'
        "}\n"
    ),
}

PHASER_MATTER_DEMO_SOURCE: dict[str, str] = {
    "src/main.ts": (
        "// @ts-nocheck — §26.7 固定 demo，验证 phaser + matter-js 依赖解析与构建\n"
        'import Phaser from "phaser";\n'
        'import Matter from "matter-js";\n\n'
        "class DemoScene extends Phaser.Scene {\n"
        "  create() {\n"
        '    this.add.text(16, 16, "Phaser + Matter demo");\n'
        "    const engine = Matter.Engine.create();\n"
        "    Matter.Engine.run(engine);\n"
        "  }\n"
        "}\n\n"
        "new Phaser.Game({\n"
        "  type: Phaser.AUTO,\n"
        "  width: 480,\n"
        "  height: 320,\n"
        "  scene: DemoScene,\n"
        "});\n"
    ),
}
