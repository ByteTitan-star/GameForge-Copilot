"""P2 pipeline.run_project 单元测试（mock builder）。"""

import pytest
from app.forge.build.dependency_preparer import DependencyPreparer, PrepareResult
from app.forge.build.pipeline import BuildPipeline
from app.forge.build.routing import BuildRouting
from app.sandbox.builder import BuilderRunResult


class StubPreparer(DependencyPreparer):
    def __init__(self) -> None:
        super().__init__(builder=RecordingBuilder(BuilderRunResult(ok=True)))

    async def prepare(self, workspace, profile):  # noqa: ANN001
        (workspace / "pnpm-lock.yaml").write_text("lockfile: 1\n", encoding="utf-8")
        return PrepareResult(ok=True, logs="prep")


class RecordingBuilder:
    def __init__(self, result: BuilderRunResult) -> None:
        self.result = result

    async def run(self, workspace, cmd, *, network_mode: str, store_readonly: bool):  # noqa: ANN001
        dist = workspace / "dist"
        dist.mkdir(exist_ok=True)
        (dist / "index.html").write_text('<script src="./assets/a.js"></script>', encoding="utf-8")
        (dist / "assets").mkdir(exist_ok=True)
        (dist / "assets" / "a.js").write_bytes(b"js")
        return self.result


@pytest.mark.asyncio
async def test_run_project_success_with_mock_builder() -> None:
    routing = BuildRouting(
        build="vite",
        renderer="phaser3",
        dependencies=("matter-js",),
    )
    source = {"src/main.ts": "console.log('ok')"}
    result = await BuildPipeline(
        preparer=StubPreparer(),
        builder=RecordingBuilder(BuilderRunResult(ok=True, logs="built")),
    ).run_project(source, routing)

    assert result.ok, result.error
    assert "index.html" in result.dist
    assert result.source == {"src/main.ts": b"console.log('ok')"}
    assert "package.json" in result.build_snapshot
