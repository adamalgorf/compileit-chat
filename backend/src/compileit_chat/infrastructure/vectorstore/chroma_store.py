"""Persistent local Chroma collection holding chunk embeddings and metadata."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from compileit_chat.domain.documents import Chunk, Language, ScoredChunk

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from chromadb.api import ClientAPI
    from chromadb.api.models.Collection import Collection

_BATCH_SIZE = 500


class ChromaVectorStore:
    """Embeddings are computed by the caller (`EmbeddingPort`); Chroma only stores and searches.

    Chroma calls are synchronous, so they run in a worker thread to keep the event loop free.
    """

    def __init__(self, path: Path, collection_name: str = "compileit_chunks") -> None:
        self._client: ClientAPI = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._name = collection_name

    async def replace_all(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Every chunk needs exactly one embedding.")
        await asyncio.to_thread(self._replace_all, chunks, embeddings)

    async def count(self) -> int:
        return await asyncio.to_thread(lambda: self._collection().count())

    async def search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        return await asyncio.to_thread(self._search, embedding, k)

    async def all_chunks(self) -> list[Chunk]:
        result = await asyncio.to_thread(
            lambda: self._collection().get(include=["documents", "metadatas"])
        )
        return [
            _to_chunk(text, metadata)
            for text, metadata in zip(
                result["documents"] or [], result["metadatas"] or [], strict=True
            )
        ]

    def _replace_all(self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]) -> None:
        # Build the new collection under a temporary name, then swap, so a failed rebuild
        # leaves the previous index intact.
        staging_name = f"{self._name}__staging"
        self._delete_if_exists(staging_name)
        staging = self._create(staging_name)
        for start in range(0, len(chunks), _BATCH_SIZE):
            batch = chunks[start : start + _BATCH_SIZE]
            vectors: list[Sequence[float]] = list(embeddings[start : start + _BATCH_SIZE])
            staging.add(
                ids=[chunk.id for chunk in batch],
                embeddings=vectors,
                documents=[chunk.text for chunk in batch],
                metadatas=[_to_metadata(chunk) for chunk in batch],
            )
        self._delete_if_exists(self._name)
        staging.modify(name=self._name)

    def _search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        collection = self._collection()
        if collection.count() == 0:
            return []
        query: list[Sequence[float]] = [embedding]
        result = collection.query(
            query_embeddings=query,
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        documents = (result["documents"] or [[]])[0]
        metadatas = (result["metadatas"] or [[]])[0]
        distances = (result["distances"] or [[]])[0]
        return [
            ScoredChunk(chunk=_to_chunk(text, metadata), score=1.0 - distance)
            for text, metadata, distance in zip(documents, metadatas, distances, strict=True)
        ]

    def _collection(self) -> Collection:
        return self._client.get_or_create_collection(
            self._name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
        )

    def _create(self, name: str) -> Collection:
        return self._client.create_collection(
            name, configuration={"hnsw": {"space": "cosine"}}, embedding_function=None
        )

    def _delete_if_exists(self, name: str) -> None:
        if name in {collection.name for collection in self._client.list_collections()}:
            self._client.delete_collection(name)


def _to_metadata(chunk: Chunk) -> dict[str, str | int]:
    # Chroma metadata values cannot be None.
    return {
        "url": chunk.document_url,
        "title": chunk.title,
        "section_heading": chunk.section_heading or "",
        "lang": chunk.lang.value,
        "crawled_at": chunk.crawled_at.isoformat(),
        "position": chunk.position,
    }


def _to_chunk(text: str | None, metadata: Mapping[str, Any] | None) -> Chunk:
    if text is None or metadata is None:
        raise ValueError("Chroma returned a chunk without text or metadata.")
    return Chunk(
        document_url=str(metadata["url"]),
        title=str(metadata["title"]),
        section_heading=str(metadata["section_heading"]) or None,
        text=text,
        lang=Language(str(metadata["lang"])),
        crawled_at=datetime.fromisoformat(str(metadata["crawled_at"])),
        position=int(metadata["position"]),
    )
