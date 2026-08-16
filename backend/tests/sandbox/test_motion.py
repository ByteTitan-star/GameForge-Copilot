"""Motion probe helpers."""

from app.sandbox.motion import png_frames_differ


def test_identical_png_bytes_not_motion() -> None:
    assert not png_frames_differ(b"\x89PNG\r\n", b"\x89PNG\r\n")


def test_sparse_diff_detects_change() -> None:
    a = bytes([0] * 500)
    b = bytearray([0] * 500)
    for i in range(0, 500, 17):
        b[i] = 1
    assert png_frames_differ(a, bytes(b))
