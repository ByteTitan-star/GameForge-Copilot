"""BuildPipeline 单元测试（mock preparer/builder，不跑真实构建）。"""

from pathlib import Path

import pytest

from app.forge.build.constants import BUILD_SNAPSHOT_FILES
from app.forge.build.dependency_preparer import DependencyPreparer, PrepareResult
from app.forge.build.pipeline import BuildPipeline
from app.forge.build.profile import BuildProfile
from app.sandbox.builder import BuilderRunResult


class StubPreparer(DependencyPreparer):
    def __init__(self, result: PrepareResult) -> None:
        super().__init__(builder=RecordingBuilder(BuilderRunResult(ok=True)))
        self._stub_result = result
        self.prepare_calls = 0

    async def prepare(self, workspace: Path, profile: BuildProfile) -> PrepareResult:
        self.prepare_calls += 1
        if self._stub_result.ok:
            (workspace / "build-profile.json").write_text(profile.to_json(), encoding="utf-8")
            (workspace / "pnpm-lock.yaml").write_text("lockfile: 1\n", encoding="utf-8")
        return self._stub_result


class RecordingBuilder:
    def __init__(
        self,
        result: BuilderRunResult,
        *,
        dist_mode: str = "full",
    ) -> None:
        self.result = result
        self.dist_mode = dist_mode
        self.calls: list[dict] = []

    async def run(self, workspace: Path, cmd, *, network_mode: str, store_readonly: bool):
        self.calls.append(
            {"cmd": list(cmd), "network_mode": network_mode, "store_readonly": store_readonly}
        )
        if self.result.ok and self.dist_mode != "none":
            dist = workspace / "dist"
            dist.mkdir(exist_ok=True)
            if self.dist_mode == "full":
                (dist / "index.html").write_text(
                    '<script src="./assets/app.js"></script>',
                    encoding="utf-8",
                )
                assets = dist / "assets"
                assets.mkdir(exist_ok=True)
                (assets / "app.js").write_bytes(b"console.log(1)")
            for name in ("package.json", "vite.config.ts", "tsconfig.json", "pnpm-workspace.yaml"):
                (workspace / name).write_text("{}", encoding="utf-8")
        return self.result


@pytest.mark.asyncio
async def test_pipeline_prepare_failure_short_circuits() -> None:
    prep = PrepareResult(ok=False, error="prepare failed", logs="x")
    pipeline = BuildPipeline(
        preparer=StubPreparer(prep),
        builder=RecordingBuilder(BuilderRunResult(ok=True)),
    )
    result = await pipeline.run_vite_ts_demo()
    assert not result.ok
    assert result.error == "prepare failed"
    assert result.dist == {}
    assert pipeline._preparer.prepare_calls == 1  # type: ignore[attr-defined]
    assert pipeline._builder.calls == []  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pipeline_build_failure() -> None:
    prep = PrepareResult(ok=True, logs="prepared")
    builder = RecordingBuilder(BuilderRunResult(ok=False, logs="build err", error="构建退出码 2"))
    pipeline = BuildPipeline(preparer=StubPreparer(prep), builder=builder)
    result = await pipeline.run_vite_ts_demo()
    assert not result.ok
    assert result.error == "构建退出码 2"
    assert "prepared" in result.logs
    assert "build err" in result.logs
    assert builder.calls[0]["network_mode"] == "none"
    assert builder.calls[0]["store_readonly"] is True
    assert "--frozen-store" in builder.calls[0]["cmd"][2]


@pytest.mark.asyncio
async def test_pipeline_missing_index_in_dist() -> None:
    prep = PrepareResult(ok=True)
    builder = RecordingBuilder(BuilderRunResult(ok=True), dist_mode="empty")
    pipeline = BuildPipeline(preparer=StubPreparer(prep), builder=builder)
    result = await pipeline.run_vite_ts_demo()
    assert not result.ok
    assert result.error == "dist 缺少 index.html"


@pytest.mark.asyncio
async def test_pipeline_success_collects_dist_and_snapshot() -> None:
    prep = PrepareResult(ok=True, logs="prep ok")
    builder = RecordingBuilder(BuilderRunResult(ok=True, logs="build ok"))
    pipeline = BuildPipeline(preparer=StubPreparer(prep), builder=builder)
    result = await pipeline.run_vite_ts_demo()

    assert result.ok
    assert "index.html" in result.dist
    assert any(k.startswith("assets/") for k in result.dist)
    assert "pnpm-lock.yaml" in result.build_snapshot
    for name in BUILD_SNAPSHOT_FILES:
        if name in result.build_snapshot:
            assert result.build_snapshot[name]
    html = result.dist["index.html"].decode("utf-8")
    assert "./assets/" in html
    assert result.prepare is not None
    assert result.prepare.ok
