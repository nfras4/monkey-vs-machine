"""Shared pytest fixtures + sys.path setup so `pytest` works without an install."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
