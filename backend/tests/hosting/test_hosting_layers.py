"""hosting 三层产物写入测试。"""

import uuid
from pathlib import Path

import pytest
from app.core.errors import AppError
from app.hosting import local as local_store


@pytest.mark.asyncio
async def test_write_version_layers_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.core.config.settings.hosting_root", str(tmp_path))
    gid = uuid.uuid4()
    version = 1
    await local_store.write_version_layers(
        gid,
        version,
        source={"src/main.ts": b"console.log(1)"},
        build_snapshot={"package.json": b"{}"},
        dist={"index.html": b"<html></html>", "assets/app.js": b"js"},
    )
    base = local_store.artifact_dir(gid, version)
    assert (base / "index.html").is_file()
    assert (base / "assets" / "app.js").is_file()
    assert (base / "source" / "src" / "main.ts").is_file()
    assert (base / "build" / "package.json").is_file()


@pytest.mark.asyncio
async def test_write_version_layers_rejects_oversized_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.core.config.settings.hosting_root", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.source_artifact_max_size_mb", 0)
    gid = uuid.uuid4()
    with pytest.raises(AppError, match="source"):
        await local_store.write_version_layers(
            gid,
            1,
            source={"src/main.ts": b"x"},
            build_snapshot={"package.json": b"{}"},
            dist={"index.html": b"<html></html>"},
        )


@pytest.mark.asyncio
async def test_write_version_layers_excludes_node_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§26.11：持久化产物不含 node_modules。"""
    monkeypatch.setattr("app.core.config.settings.hosting_root", str(tmp_path))
    gid = uuid.uuid4()
    await local_store.write_version_layers(
        gid,
        1,
        source={"src/main.ts": b"x"},
        build_snapshot={"package.json": b"{}"},
        dist={"index.html": b"<html></html>", "assets/app.js": b"js"},
    )
    base = local_store.artifact_dir(gid, 1)
    for path in base.rglob("*"):
        rel = path.relative_to(base).as_posix()
        assert "node_modules" not in rel.split("/")
        assert ".pnpm-store" not in rel.split("/")
