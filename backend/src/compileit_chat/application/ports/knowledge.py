"""Ports for storing and searching the ingested website content."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Sequence

    from compileit_chat.domain.documents import Chunk, Document, ScoredChunk


class EmbeddingPort(Protocol):
    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class VectorStorePort(Protocol):
    async def replace_all(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]
    ) -> None:
        """Atomically swap the indexed content, so pages removed from the site disappear."""
        ...

    async def search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]: ...

    async def all_chunks(self) -> list[Chunk]:
        """Every indexed chunk; lexical retrievers build their index from this."""
        ...


class DocumentStorePort(Protocol):
    """Full page texts keyed by URL, for reading or summarising a whole page."""

    async def replace_all(self, documents: Sequence[Document]) -> None: ...

    async def get(self, url: str) -> Document | None: ...

    async def list_all(self) -> list[Document]: ...


class RetrieverPort(Protocol):
    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        """The `k` most relevant chunks for a natural-language query, best first."""
        ...
