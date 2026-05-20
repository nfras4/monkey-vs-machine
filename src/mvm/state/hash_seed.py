"""Deterministic SHA256-based seeding."""
from __future__ import annotations

import hashlib

DEFAULT_SEED_STRING = "mvm-genesis"


def hash_seed(*args: object, seed_string: str = DEFAULT_SEED_STRING) -> int:
    """Return a stable uint64 seed derived from SHA256 of `seed_string:arg1:arg2:...`.

    Args are coerced to str; order matters. The same inputs always give the
    same output across numpy/sklearn/python versions.
    """
    payload = seed_string + ":" + ":".join(str(a) for a in args)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")
