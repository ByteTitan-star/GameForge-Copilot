"""扫描暂存区，拦截疑似密钥/凭据进仓。"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 高置信度模式；故意不扫通用 UUID / 短 hex，减少误报。
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "generic_api_key_assign",
        re.compile(
            r"(?i)(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{16,}['\"]"
        ),
    ),
    ("bearer_token", re.compile(r"(?i)bearer\s+[a-z0-9\-._~+/]+=*")),
]

_SKIP_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".lock",
    ".woff",
    ".woff2",
}

# Test fixtures may embed fake keys (e.g. private_key sample for the scanner itself).
_SKIP_PATH_PREFIXES = (
    "backend/tests/",
)


def _staged_files() -> list[Path]:
    out = subprocess.check_output(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return [Path(line.strip()) for line in out.splitlines() if line.strip()]


def _scan_text(path: Path, text: str) -> list[str]:
    hits: list[str] = []
    for name, pat in _PATTERNS:
        if pat.search(text):
            hits.append(f"{path.as_posix()}: matched {name}")
    return hits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--staged",
        action="store_true",
        help="只扫描 git 暂存区文件（pre-commit 使用）",
    )
    args = parser.parse_args(argv)

    files = _staged_files() if args.staged else []
    if args.staged and not files:
        return 0

    findings: list[str] = []
    for path in files:
        if not path.is_file() or path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        posix = path.as_posix()
        if any(posix.startswith(prefix) for prefix in _SKIP_PATH_PREFIXES):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        findings.extend(_scan_text(path, text))

    if findings:
        print("secret-scan: 疑似密钥/凭据，请移出暂存区：", file=sys.stderr)
        for line in findings:
            print(f"  - {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
