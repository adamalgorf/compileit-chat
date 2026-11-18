import pytest

from compileit_chat.application.errors import IngestionError
from compileit_chat.application.use_cases import BuildIndex, IndexReport
from tests.fakes import (
    InMemoryDocumentStore,
    InMemoryVectorStore,
    LengthEmbeddings,
    ParagraphChunker,
    make_document,
)


async def test_indexes_every_chunk_with_contextual_text() -> None:
    documents = InMemoryDocumentStore(
        [
            make_document("https://compileit.com/kontakt", "Stockholm\n\nKalmar", "Kontakt"),
            make_document("https://compileit.com/om-oss", "Vår story", "Om oss"),
        ]
    )
    embeddings, vectors = LengthEmbeddings(), InMemoryVectorStore()

    report = await BuildIndex(documents, ParagraphChunker(), embeddings, vectors).execute()

    assert report == IndexReport(documents=2, chunks=3)
    assert [c.text for c in vectors.chunks] == ["Stockholm", "Kalmar", "Vår story"]
    assert embeddings.embedded[0] == "Kontakt\n\nStockholm"  # title gives the chunk context
    assert len(vectors.embeddings) == 3


async def test_refuses_to_wipe_the_index_when_there_are_no_documents() -> None:
    vectors = InMemoryVectorStore()

    with pytest.raises(IngestionError):
        await BuildIndex(
            InMemoryDocumentStore(), ParagraphChunker(), LengthEmbeddings(), vectors
        ).execute()


async def test_ensure_built_builds_only_when_the_index_is_empty() -> None:
    documents = InMemoryDocumentStore([make_document("https://compileit.com", "Hej")])
    embeddings, vectors = LengthEmbeddings(), InMemoryVectorStore()
    use_case = BuildIndex(documents, ParagraphChunker(), embeddings, vectors)

    first, second = await use_case.ensure_built(), await use_case.ensure_built()

    assert first == IndexReport(documents=1, chunks=1)
    assert second is None
    assert len(embeddings.embedded) == 1  # embedded once
