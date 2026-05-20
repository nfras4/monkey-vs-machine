"""VADER sentiment over headlines."""
from __future__ import annotations

from typing import Iterable, List

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def compound_scores(texts: Iterable[str]) -> List[float]:
    return [_analyzer.polarity_scores(t)["compound"] for t in texts]


def mean_compound(texts: Iterable[str]) -> float:
    scores = compound_scores(texts)
    if not scores:
        return 0.0
    return sum(scores) / len(scores)
