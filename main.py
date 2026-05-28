#!/usr/bin/env python3
"""Compatibility entrypoint for `python3 main.py` deployments."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from agent_news.main import main


if __name__ == "__main__":
    main()

