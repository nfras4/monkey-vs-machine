"""Canonical SHA256 of a feature DataFrame.

Hashes the sorted long-form representation so column order and row order
don't change the result. Used to detect silent feature drift across runs.
"""
from __future__ import annotations

import hashlib

import pandas as pd


def features_hash(df: pd.DataFrame) -> str:
    if df.empty:
        return hashlib.sha256(b"empty").hexdigest()
    # Canonical form: sort columns, sort index, convert to numpy bytes.
    df_sorted = df.reindex(sorted(df.columns), axis=1).sort_index()
    arr = df_sorted.to_numpy(dtype="float64")
    h = hashlib.sha256()
    h.update(",".join(df_sorted.columns).encode("utf-8"))
    h.update(b"|")
    h.update(arr.tobytes(order="C"))
    return h.hexdigest()
