"""cdn_policy 单元测试：白名单提取 / 校验 / CSP 生成。"""

from __future__ import annotations

from app.core.cdn_policy import (
    ALLOWED_CDN_HOSTS,
    build_csp,
    extract_external_refs,
    validate_refs,
)


def test_extract_picks_http_https_refs() -> None:
    html = """
    <script src="https://cdn.jsdelivr.net/npm/three@0.160/build/three.min.js"></script>
    <link href='https://fonts.googleapis.com/css2?family=Fredoka' rel="stylesheet">
    <a href="HTTP://Example.com/x">x</a>
    """
    refs = extract_external_refs(html)
    assert "https://cdn.jsdelivr.net/npm/three@0.160/build/three.min.js" in refs
    assert "https://fonts.googleapis.com/css2?family=Fredoka" in refs
    # 大小写协议也应被收录（lower 判断、原值保留）
    assert any(r.lower().startswith("http://example.com") for r in refs)


def test_extract_ignores_relative_and_data_uri() -> None:
    html = """
    <script src="./local.js"></script>
    <script src="/abs.js"></script>
    <img src="data:image/png;base64,xxxx">
    <link href="blob:xxx">
    """
    assert extract_external_refs(html) == []


def test_extract_dedups_preserving_order() -> None:
    html = """
    <script src="https://unpkg.com/react"></script>
    <script src="https://unpkg.com/react"></script>
    <link href="https://unpkg.com/react-dom">
    """
    refs = extract_external_refs(html)
    assert refs == ["https://unpkg.com/react", "https://unpkg.com/react-dom"]


def test_validate_passes_for_allowlisted_hosts() -> None:
    refs = [
        "https://cdn.jsdelivr.net/npm/a",
        "https://fonts.gstatic.com/s/fredoka.woff2",
    ]
    ok, violations = validate_refs(refs)
    assert ok is True
    assert violations == []


def test_validate_flags_off_domain_refs() -> None:
    refs = [
        "https://cdn.jsdelivr.net/npm/a",  # OK
        "https://evil.example.com/steal.js",  # 违规
        "https://unpkg.com/p/react@18",  # OK
    ]
    ok, violations = validate_refs(refs)
    assert ok is False
    assert violations == ["https://evil.example.com/steal.js"]


def test_validate_accepts_custom_allowlist() -> None:
    ok, violations = validate_refs(["https://cdn.example.net/x"], frozenset({"cdn.example.net"}))
    assert ok is True
    assert violations == []


def test_validate_empty_is_ok() -> None:
    ok, violations = validate_refs([])
    assert ok is True
    assert violations == []


def test_build_csp_contains_every_allowlisted_host() -> None:
    csp = build_csp()
    for host in ALLOWED_CDN_HOSTS:
        assert host in csp, f"CSP 缺少白名单域 {host}"
    assert "default-src 'self'" in csp
    assert "script-src" in csp
    assert "img-src 'self' data: blob:" in csp


def test_build_csp_has_no_wildcard_https() -> None:
    # 收敛后不应再出现宽松的 https: 通配（旧策略的风险点）
    csp = build_csp()
    assert "https:" not in csp


def test_build_csp_allows_blob_workers() -> None:
    """Tone.js 等音频库会在 sandbox iframe 内创建 blob: worker。"""
    csp = build_csp()
    assert "worker-src 'self' blob:" in csp
