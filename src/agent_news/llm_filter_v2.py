"""Compatibility wrapper for the Relevance Filter V2 agent workspace module."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_WORKSPACE_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / 'agents'
    / 'relevance_filter_v2'
    / 'workspace'
    / 'llm_filter_v2.py'
)

_spec = importlib.util.spec_from_file_location(__name__, _WORKSPACE_MODULE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load agent workspace module: {_WORKSPACE_MODULE_PATH}")

_module = importlib.util.module_from_spec(_spec)
sys.modules[__name__] = _module
_spec.loader.exec_module(_module)
