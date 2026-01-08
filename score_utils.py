"""Utility helpers for score normalization."""

from typing import Dict


def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Normalize a dict of scores to the [0, 1] range.

    When all scores are identical, every entry receives 1.0 to avoid divide-by-zero.
    """
    if not scores:
        return {}
    values = list(scores.values())
    min_score = min(values)
    max_score = max(values)
    if max_score == min_score:
        return {key: 1.0 for key in scores}
    denom = max_score - min_score
    return {key: (value - min_score) / denom for key, value in scores.items()}
