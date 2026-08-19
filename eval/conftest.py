"""Shared fixtures for eval runners."""

from __future__ import annotations

import json
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
DATASETS_DIR = EVAL_ROOT / "datasets"
REPORTS_DIR = EVAL_ROOT / "reports"
DOCS_EVALS_DIR = EVAL_ROOT.parent / "docs" / "evals"

REPORTS_DIR.mkdir(exist_ok=True)
DOCS_EVALS_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset(name: str) -> list[dict]:
    path = DATASETS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))
