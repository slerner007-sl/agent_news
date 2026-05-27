"""Add the local src layout to sys.path for standalone scripts."""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap() -> None:
    src_path = Path(__file__).resolve().parents[1] / "src"
    src_text = str(src_path)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

