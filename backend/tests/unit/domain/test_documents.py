from dataclasses import replace
from datetime import UTC, datetime

from compileit_chat.domain.documents import Chunk, Document, Language, SourceRef

NOW = datetime(2026, 11, 17, tzinfo=UTC)


def make_document(text: str, url: str = "https://www.compileit.com/om-oss") -> Document:
    return Document(url=url, title="Om oss", text=text, lang=Language.SWEDISH, crawled_at=NOW)


def make_chunk(position: int, url: str = "https://www.compileit.com/om-oss") -> Chunk:
    return Chunk(
        document_url=url,
        title="Om oss",
        section_heading="Vår historia",
        text="Compileit grundades ...",
        lang=Language.SWEDISH,
        crawled_at=NOW,
        position=position,
    )


def test_content_hash_ignores_whitespace_and_case() -> None:
    a = make_document("# Om oss\n\nVi  bygger   AI.")
    b = make_document("# om oss vi bygger ai.", url="https://www.compileit.com/en/about")

    assert a.content_hash == b.content_hash


def test_content_hash_differs_for_different_content() -> None:
    assert (
        make_document("Vi bygger AI.").content_hash
        != make_document("Vi bygger appar.").content_hash
    )


def test_document_source() -> None:
    assert make_document("x").source == SourceRef("Om oss", "https://www.compileit.com/om-oss")


def test_chunk_id_is_deterministic_and_unique_per_position() -> None:
    first = make_chunk(0)

    assert first.id == replace(first, text="changed").id
    assert first.id != make_chunk(1).id
    assert first.id != make_chunk(0, url="https://www.compileit.com/kontakt").id
