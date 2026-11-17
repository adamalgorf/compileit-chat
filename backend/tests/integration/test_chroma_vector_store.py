from pathlib import Path

import pytest

from compileit_chat.infrastructure.vectorstore.chroma_store import ChromaVectorStore
from tests.fakes import ParagraphChunker, make_document

CHUNKS = ParagraphChunker().split(
    make_document("https://compileit.com/kontakt", "Stockholm\n\nKalmar\n\nSkövde", "Kontakt")
)
VECTORS = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]


@pytest.fixture
def store(tmp_path: Path) -> ChromaVectorStore:
    return ChromaVectorStore(tmp_path / "chroma")


async def test_search_returns_nearest_chunks_with_metadata(store: ChromaVectorStore) -> None:
    await store.replace_all(CHUNKS, VECTORS)

    hits = await store.search([0.0, 1.0], k=2)

    assert [hit.chunk for hit in hits] == [CHUNKS[1], CHUNKS[2]]
    assert hits[0].score == pytest.approx(1.0)
    assert hits[0].score > hits[1].score


async def test_replace_all_swaps_content_and_persists(
    store: ChromaVectorStore, tmp_path: Path
) -> None:
    await store.replace_all(CHUNKS, VECTORS)
    await store.replace_all(CHUNKS[:1], VECTORS[:1])

    reopened = ChromaVectorStore(tmp_path / "chroma")

    assert await reopened.count() == 1
    assert await reopened.all_chunks() == CHUNKS[:1]


async def test_empty_store(store: ChromaVectorStore) -> None:
    assert await store.count() == 0
    assert await store.search([1.0, 0.0], k=3) == []


async def test_rejects_mismatched_embeddings(store: ChromaVectorStore) -> None:
    with pytest.raises(ValueError, match="exactly one embedding"):
        await store.replace_all(CHUNKS, VECTORS[:1])
