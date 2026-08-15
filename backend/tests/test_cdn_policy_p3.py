"""P3 dist CSP / URL 扫描测试。"""

from pathlib import Path

from app.core.cdn_policy import (
    build_csp_project,
    scan_dist_external_refs,
    validate_dist_self_contained,
)


def test_build_csp_project_is_self_only() -> None:
    csp = build_csp_project()
    assert "script-src 'self'" in csp
    assert "connect-src 'none'" in csp
    assert "cdn.jsdelivr.net" not in csp


def test_scan_dist_external_refs(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        '<html><script src="./assets/app.js"></script></html>', encoding="utf-8"
    )
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text(
        'fetch("https://evil.example/api")', encoding="utf-8"
    )
    refs = scan_dist_external_refs(dist)
    assert refs == ["https://evil.example/api"]
    ok, violations = validate_dist_self_contained(refs)
    assert not ok
    assert violations
