"""S3/OSS 托管配置与对象 key 的纯本地测试。"""

import uuid

import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.hosting.s3 import S3HostingBackend, _object_key


def test_object_key_uses_prefix_and_rejects_traversal() -> None:
    game_id = uuid.uuid4()
    assert _object_key("/gameforge/", game_id, 3, "assets/main.js") == (
        f"gameforge/{game_id}/3/assets/main.js"
    )
    with pytest.raises(AppError):
        _object_key("gameforge", game_id, 3, "../secret.txt")


def test_s3_backend_rejects_missing_required_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "s3_endpoint", "")
    monkeypatch.setattr(settings, "s3_region", "")
    monkeypatch.setattr(settings, "s3_bucket", "")
    monkeypatch.setattr(settings, "s3_ak", "")
    monkeypatch.setattr(settings, "s3_sk", "")

    with pytest.raises(AppError, match="S3 托管缺少配置"):
        S3HostingBackend()
