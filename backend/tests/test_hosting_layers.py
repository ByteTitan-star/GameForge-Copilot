"""hosting 三层产物写入测试。"""

import uuid
from pathlib import Path

import pytest

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
