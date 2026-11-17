"""(Re)build the search index from the stored documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from compileit_chat.application.errors import IngestionError

if TYPE_CHECKING:
    from compileit_chat.application.ports import (
        ChunkerPort,
        DocumentStorePort,
        EmbeddingPort,
        VectorStorePort,
    )


@dataclass(frozen=True, slots=True)
class IndexReport:
    documents: int
    chunks: int


class BuildIndex:
    """Chunk every stored document, embed the chunks and replace the vector index."""

    def __init__(
        self,
        documents: DocumentStorePort,
        chunker: ChunkerPort,
        embeddings: EmbeddingPort,
        vector_store: VectorStorePort,
    ) -> None:
        self._documents = documents
        self._chunker = chunker
        self._embeddings = embeddings
        self._vector_store = vector_store

    async def execute(self) -> IndexReport:
        documents = await self._documents.list_all()
        if not documents:
            raise IngestionError("No documents to index. Run the crawl first.")
        chunks = [chunk for document in documents for chunk in self._chunker.split(document)]
        vectors = await self._embeddings.embed_documents([chunk.search_text for chunk in chunks])
        await self._vector_store.replace_all(chunks, vectors)
        return IndexReport(documents=len(documents), chunks=len(chunks))
