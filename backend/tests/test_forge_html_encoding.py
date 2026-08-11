"""Regression coverage for generated HTML with malformed text bytes."""

import logging

from app.forge.graph import _read_html_text


def test_read_html_replaces_invalid_utf8_bytes(
    tmp_path, caplog
) -> None:
    html_path = tmp_path / "index.html"
    html_path.write_bytes(b"<html><body>broken: \xb7</body></html>")

    with caplog.at_level(logging.WARNING, logger="app.forge.graph"):
        html = _read_html_text(html_path)

    assert html == "<html><body>broken: \ufffd</body></html>"
    assert "generated HTML is not valid UTF-8" in caplog.text
