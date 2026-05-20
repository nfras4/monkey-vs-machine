"""Capture the (python, lib, lockfile) fingerprint per tick.

Stored in `ai_model_history.runtime_fingerprint` so a future replay knows
whether the environment matches. Bit-identical reruns are guaranteed only
when the fingerprint matches.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
from pathlib import Path
from typing import Dict

from .config import PROJECT_ROOT

REQUIREMENTS_FILE = PROJECT_ROOT / "requirements.txt"
_COMMENT_OR_BLANK = re.compile(r"^\s*(#|$)")


def _lockfile_sha256() -> str:
    if not REQUIREMENTS_FILE.exists():
        return ""
    h = hashlib.sha256()
    with REQUIREMENTS_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            if _COMMENT_OR_BLANK.match(line):
                continue
            h.update(line.strip().encode("utf-8"))
            h.update(b"\n")
    return h.hexdigest()


def _blas_info() -> str:
    """Best-effort BLAS identifier. Don't import numpy lazily — it's already loaded."""
    try:
        import numpy as np
        cfg = np.show_config(mode="dicts") if hasattr(np, "show_config") else None
        if isinstance(cfg, dict):
            for key in ("blas", "blas_info", "openblas_info", "blas_opt_info"):
                section = cfg.get(key) or cfg.get("Build Dependencies", {}).get(key)
                if isinstance(section, dict):
                    name = section.get("name") or section.get("found")
                    if name:
                        return str(name)
        return "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _version(module_name: str) -> str:
    try:
        mod = __import__(module_name)
        return getattr(mod, "__version__", "unknown")
    except Exception:  # noqa: BLE001
        return "missing"


def runtime_fingerprint() -> Dict[str, str]:
    """Return a JSON-serialisable map describing the runtime."""
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "numpy": _version("numpy"),
        "sklearn": _version("sklearn"),
        "pandas": _version("pandas"),
        "pyarrow": _version("pyarrow"),
        "yfinance": _version("yfinance"),
        "lockfile_sha256": _lockfile_sha256(),
        "blas": _blas_info(),
        "threads": str(os.cpu_count() or 0),
    }
