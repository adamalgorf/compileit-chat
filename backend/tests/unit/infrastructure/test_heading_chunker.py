"""Chunker tests use a word counter (1 word = 1 token) so sizes are easy to reason about."""

from datetime import UTC, datetime

import pytest

from compileit_chat.domain.documents import Document, Language
from compileit_chat.infrastructure.chunking.heading_chunker import HeadingAwareChunker


def count_words(text: str) -> int:
    return len(text.split())


def words(n: int, word: str = "ord") -> str:
    return " ".join([word] * n)


def make_document(text: str) -> Document:
    return Document(
        url="https://compileit.com/om-oss",
        title="Om oss",
        text=text,
        lang=Language.SWEDISH,
        crawled_at=datetime(2026, 11, 17, tzinfo=UTC),
    )


def chunker(target: int = 10, maximum: int = 20, overlap: int = 0) -> HeadingAwareChunker:
    return HeadingAwareChunker(count_words, target, maximum, overlap)


def test_small_document_is_one_chunk_with_metadata() -> None:
    document = make_document(f"# Om oss\n\n{words(5)}")

    [chunk] = chunker().split(document)

    assert chunk.text == f"# Om oss\n\n{words(5)}"
    assert (chunk.title, chunk.section_heading, chunk.position) == ("Om oss", "Om oss", 0)
    assert (chunk.document_url, chunk.lang) == (document.url, document.lang)


def test_new_section_starts_new_chunk_once_target_is_reached() -> None:
    text = f"# A\n\n{words(12, 'a')}\n\n## B\n\n{words(3, 'b')}\n\n## C\n\n{words(3, 'c')}"

    chunks = chunker(target=10, maximum=40).split(make_document(text))

    assert [c.text for c in chunks] == [
        f"# A\n\n{words(12, 'a')}",
        f"## B\n\n{words(3, 'b')}\n\n## C\n\n{words(3, 'c')}",  # B is below target: C joins it
    ]
    assert [c.section_heading for c in chunks] == ["A", "A > B"]


def test_chunks_never_exceed_max_and_headings_move_with_their_content() -> None:
    text = f"# A\n\n{words(8, 'a')}\n\n{words(8, 'b')}\n\n## B\n\n{words(8, 'c')}"

    chunks = chunker(target=20, maximum=20).split(make_document(text))

    assert all(count_words(c.text) <= 20 for c in chunks)
    assert chunks[-1].text.startswith("## B")


def test_oversized_paragraph_is_split_by_sentence() -> None:
    sentences = [f"{words(6, w)}." for w in ("a", "b", "c", "d")]

    chunks = chunker(target=10, maximum=13).split(make_document(" ".join(sentences)))

    assert [c.text for c in chunks] == [
        f"{sentences[0]} {sentences[1]}",
        f"{sentences[2]} {sentences[3]}",
    ]


def test_overlap_repeats_trailing_paragraph_when_cut_mid_section() -> None:
    text = f"# A\n\n{words(9, 'a')}\n\n{words(3, 'b')}\n\n{words(9, 'c')}"

    chunks = chunker(target=10, maximum=15, overlap=4).split(make_document(text))

    assert [c.text for c in chunks] == [
        f"# A\n\n{words(9, 'a')}\n\n{words(3, 'b')}",
        f"{words(3, 'b')}\n\n{words(9, 'c')}",
    ]
    assert [c.position for c in chunks] == [0, 1]


def test_heading_only_document_yields_no_chunks() -> None:
    assert chunker().split(make_document("# Tom sida\n\n## Ingenting här")) == []


@pytest.mark.parametrize(("target", "maximum", "overlap"), [(0, 10, 0), (20, 10, 0), (10, 20, 10)])
def test_rejects_inconsistent_sizes(target: int, maximum: int, overlap: int) -> None:
    with pytest.raises(ValueError, match="Require"):
        HeadingAwareChunker(count_words, target, maximum, overlap)
