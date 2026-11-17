"""Tokenizer, BM25 and rank fusion: the pure building blocks of hybrid retrieval."""

import pytest

from compileit_chat.infrastructure.retrieval.bm25 import BM25Index
from compileit_chat.infrastructure.retrieval.fusion import reciprocal_rank_fusion
from compileit_chat.infrastructure.retrieval.tokenizer import SwedishTokenizer

tokenize = SwedishTokenizer()


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Vad erbjuder ni för typer av AI-tjänster?", ["erbjud", "typ", "ai", "tjänst"]),
        ("Vilka branscher jobbar ni med?", ["bransch", "jobb"]),
        ("Kundserviceagent01", ["kundserviceagent", "01"]),
        ("hello@compileit.com", ["hello", "compileit", "com"]),
    ],
)
def test_tokenizer_folds_case_drops_stop_words_and_stems(text: str, expected: list[str]) -> None:
    assert tokenize(text) == expected


def test_tokenizer_matches_singular_and_plural() -> None:
    assert tokenize("tjänst") == tokenize("tjänster")


def test_bm25_prefers_rarer_terms_and_ignores_non_matching_documents() -> None:
    corpus = [["ai", "agent", "kundservic"], ["ai", "app"], ["ai", "webb"], ["kontor", "kalmar"]]

    hits = BM25Index(corpus).top(["ai", "agent"], n=10)

    assert [index for index, _ in hits] == [0, 1, 2]  # "agent" is rare, so doc 0 wins
    assert all(score > 0 for _, score in hits)


def test_bm25_normalises_for_document_length() -> None:
    corpus = [["säker"], ["säker", *["fyll"] * 20], ["annat"]]

    [(best, _), _] = BM25Index(corpus).top(["säker"], n=10)

    assert best == 0


def test_bm25_handles_empty_corpus_and_unknown_terms() -> None:
    assert BM25Index([]).top(["ai"], n=5) == []
    assert BM25Index([["ai"]]).top(["tesla"], n=5) == []


def test_rrf_rewards_agreement_between_rankings() -> None:
    # "b" is only second in each list, but both lists agree on it.
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "b"]], k=60)

    assert [item for item, _ in fused] == ["b", "a", "c"]
    assert fused[0][1] == pytest.approx(2 / 62)


def test_rrf_keeps_first_seen_order_on_ties() -> None:
    assert [item for item, _ in reciprocal_rank_fusion([["a"], ["b"]])] == ["a", "b"]
