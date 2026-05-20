"""Model registry — council v2.2.

`MODELS` is a dict mapping `model_id` → builder. Each builder returns a fresh
object exposing the duck-typed interface:
    .fit(X, y, seed) -> diagnostics_dict
    .predict_proba(X) -> ndarray of shape (n_samples, 2)

No ABC, no plugin system, no YAML. Adding model #2 is one new entry.
"""
from __future__ import annotations

from typing import Callable, Dict

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance

CHAMPION_MODEL_ID = "hgb_v1"


class HgbV1Builder:
    """Default model: HistGradientBoosting classifier on hand-engineered features."""

    family = "sklearn_hgb"

    config = {
        "max_iter": 200,
        "learning_rate": 0.05,
        "max_depth": 6,
        "min_samples_leaf": 50,
    }

    def __init__(self) -> None:
        self._model: HistGradientBoostingClassifier | None = None

    def fit(self, X: np.ndarray, y: np.ndarray, seed: int) -> Dict:
        # Mask uint64 seed into int32 range that sklearn accepts.
        sk_seed = int(seed) & 0x7FFFFFFF
        model = HistGradientBoostingClassifier(
            random_state=sk_seed,
            **self.config,
        )
        model.fit(X, y)
        self._model = model

        train_score = float(model.score(X, y))
        # Permutation importance on the training set (cheap surrogate; no separate val split here).
        try:
            imp = permutation_importance(
                model, X, y,
                n_repeats=3,
                random_state=sk_seed,
                n_jobs=1,
            )
            importances = imp.importances_mean.tolist()
        except Exception:  # noqa: BLE001 — importance is non-essential
            importances = []

        return {
            "model_family": self.family,
            "train_score": train_score,
            "feature_importances": importances,
            "n_train_samples": int(X.shape[0]),
            "config": self.config,
        }

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("Builder.fit must be called before predict_proba")
        return self._model.predict_proba(X)


def build_hgb_v1() -> HgbV1Builder:
    return HgbV1Builder()


MODELS: Dict[str, Callable[[], object]] = {
    "hgb_v1": build_hgb_v1,
}
