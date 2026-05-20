"""Asserts every MODELS entry returns a builder with the duck-typed interface."""
from __future__ import annotations

import numpy as np

from mvm.models.registry import MODELS


def test_models_dict_non_empty():
    assert len(MODELS) >= 1
    assert "hgb_v1" in MODELS


def test_every_builder_has_fit_and_predict_proba():
    for model_id, fn in MODELS.items():
        builder = fn()
        assert hasattr(builder, "fit"), f"{model_id} missing .fit"
        assert hasattr(builder, "predict_proba"), f"{model_id} missing .predict_proba"


def test_builder_fit_and_predict_smoke():
    builder = MODELS["hgb_v1"]()
    rng = np.random.default_rng(0)
    X = rng.standard_normal((40, 9))
    y = (rng.random(40) > 0.5).astype(int)
    diagnostics = builder.fit(X, y, seed=42)
    assert "model_family" in diagnostics
    assert "train_score" in diagnostics
    proba = builder.predict_proba(X[:5])
    assert proba.shape == (5, 2)
