"""Okapi BM25 over a small, fixed corpus.

Written out instead of pulling in a library: it is ~30 lines, the corpus is a few hundred
chunks, and owning it keeps tokenization and scoring transparent and testable.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class BM25Index:
    def __init__(self, corpus: Sequence[Sequence[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._term_counts = [Counter(tokens) for tokens in corpus]
        self._lengths = [len(tokens) for tokens in corpus]
        self._average_length = sum(self._lengths) / len(corpus) if corpus else 0.0
        document_frequency = Counter(term for tokens in corpus for term in set(tokens))
        # Lucene's variant of IDF: always positive, even for terms in most documents.
        self._idf = {
            term: math.log(1 + (len(corpus) - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def top(self, query: Sequence[str], n: int) -> list[tuple[int, float]]:
        """`(document index, score)` of the `n` best matches with a positive score, best first."""
        scored = [(index, self._score(index, query)) for index in range(len(self._lengths))]
        matching = [(index, score) for index, score in scored if score > 0]
        return sorted(matching, key=lambda hit: hit[1], reverse=True)[:n]

    def _score(self, index: int, query: Sequence[str]) -> float:
        counts = self._term_counts[index]
        length_norm = 1 - self._b + self._b * self._lengths[index] / (self._average_length or 1)
        score = 0.0
        for term in query:
            tf = counts.get(term, 0)
            if tf:
                score += self._idf[term] * tf * (self._k1 + 1) / (tf + self._k1 * length_norm)
        return score
