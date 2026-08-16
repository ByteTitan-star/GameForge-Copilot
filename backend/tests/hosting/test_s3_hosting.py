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


def _bare_backend(prefix: str = "") -> S3HostingBackend:
    """绕过 __init__（需要 boto3/OSS 凭证），仅装配 list_files/_dir_prefix 依赖的字段。"""
    backend = S3HostingBackend.__new__(S3HostingBackend)
    backend._bucket = "bucket"
    backend._prefix = prefix.strip("/")
    return backend


def test_dir_prefix_trailing_slash_prevents_version_collision() -> None:
    """Prefix 末尾必须带 /，否则 version=1 会字符串匹配到 version=10。"""
    backend = _bare_backend(prefix="gameforge")
    gid = uuid.uuid4()
    assert backend._dir_prefix(gid, 1) == f"gameforge/{gid}/1/"
    # version=1 的前缀绝不能是 version=10 前缀的前缀
    assert backend._dir_prefix(gid, 1) != backend._dir_prefix(gid, 10)


def test_dir_prefix_without_global_prefix() -> None:
    backend = _bare_backend(prefix="")
    gid = uuid.uuid4()
    assert backend._dir_prefix(gid, 3) == f"{gid}/3/"


class _FakeS3Client:
    """模拟 boto3 list_objects_v2，按预设分页响应翻页。"""

    def __init__(self, pages: list[dict]) -> None:
        self._pages = pages
        self.calls: list[dict] = []

    def list_objects_v2(self, **kwargs: object) -> dict:
        self.calls.append(kwargs)
        return self._pages.pop(0)


async def test_s3_list_files_paginates_and_strips_prefix() -> None:
    """IsTruncated=True 时用 ContinuationToken 翻页，直到取完；返回相对路径。"""
    gid = uuid.uuid4()
    backend = _bare_backend(prefix="gameforge")
    backend._client = _FakeS3Client(
        [
            {
                "Contents": [
                    {"Key": f"gameforge/{gid}/1/index.html", "Size": 42},
                    {"Key": f"gameforge/{gid}/1/"},  # 目录占位，应被跳过
                ],
                "IsTruncated": True,
                "NextContinuationToken": "tok",
            },
            {
                "Contents": [
                    {"Key": f"gameforge/{gid}/1/assets/app.js", "Size": 7},
                ],
                "IsTruncated": False,
            },
        ]
    )

    metas = await backend.list_files(gid, 1)

    paths = [m.path for m in metas]
    assert paths == ["assets/app.js", "index.html"]  # 排序后
    assert metas[0].size == 7
    assert metas[1].mime == "text/html"

    # 第二次调用带上了 ContinuationToken
    assert backend._client.calls[1].get("ContinuationToken") == "tok"
    # 两次调用的 Prefix 都是带末尾斜杠的目录前缀
    assert all(c["Prefix"] == f"gameforge/{gid}/1/" for c in backend._client.calls)


async def test_s3_list_files_empty_when_no_objects() -> None:
    backend = _bare_backend(prefix="")
    backend._client = _FakeS3Client([{"IsTruncated": False}])
    gid = uuid.uuid4()
    assert await backend.list_files(gid, 1) == []


async def test_s3_list_files_wraps_client_error() -> None:
    backend = _bare_backend(prefix="")

    class _Boom:
        def list_objects_v2(self, **kwargs: object) -> dict:
            raise RuntimeError("oss down")

    backend._client = _Boom()
    gid = uuid.uuid4()
    with pytest.raises(AppError):
        await backend.list_files(gid, 1)
