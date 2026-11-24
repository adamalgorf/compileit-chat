"""Reciprocal Rank Fusion (Cormack et al., 2009)."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], k: int = 60
) -> list[tuple[str, float]]:
    """Merge ranked id lists: each id scores sum(1 / (k + rank)) over the lists it appears in.

    Uses ranks only, so vector cosine similarities and BM25 scores (incomparable scales)
    never need normalising. Ties keep first-seen order.

    `k` damps the head of each list: with k=60, rank 1 is worth 1/61 and rank 10 is 1/70,
    so an item found by both lists usually beats one ranked first by only one of them.
    """
    scores: defaultdict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] += 1 / (k + rank)
    return sorted(scores.items(), key=lambda entry: entry[1], reverse=True)
