"""`RetrieverPort` adapter: vector search and BM25, merged with Reciprocal Rank Fusion.

Vectors catch paraphrases ("var sitter ni?" ~ "Våra kontor"); BM25 catches exact terms that
embeddings blur (names, e-mail addresses, "Gasellpris", org numbers).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from compileit_chat.domain.documents import ScoredChunk
from compileit_chat.infrastructure.retrieval.bm25 import BM25Index
from compileit_chat.infrastructure.retrieval.fusion import reciprocal_rank_fusion

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from compileit_chat.application.ports import EmbeddingPort, VectorStorePort
    from compileit_chat.domain.documents import Chunk

type Tokenizer = Callable[[str], list[str]]


class _LexicalIndex:
    def __init__(self, chunks: Sequence[Chunk], tokenize: Tokenizer) -> None:
        self._chunks = chunks
        self._tokenize = tokenize
        self._bm25 = BM25Index([tokenize(chunk.search_text) for chunk in chunks])

    def search(self, query: str, n: int) -> list[ScoredChunk]:
        return [
            ScoredChunk(self._chunks[index], score)
            for index, score in self._bm25.top(self._tokenize(query), n)
        ]


class HybridRetriever:
    """The BM25 index is built from the vector store on first search and then cached.

    The corpus only changes on re-ingestion, which happens offline; restart to pick it up.
    """

    def __init__(
        self,
        embeddings: EmbeddingPort,
        vector_store: VectorStorePort,
        tokenize: Tokenizer,
        candidates: int = 20,
        rrf_k: int = 60,
    ) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._tokenize = tokenize
        self._candidates = candidates
        self._rrf_k = rrf_k
        self._lexical: _LexicalIndex | None = None
        self._lexical_lock = asyncio.Lock()

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        n = max(k, self._candidates)
        lexical = await self._lexical_index()
        embedding = await self._embeddings.embed_query(query)
        vector_hits = await self._vector_store.search(embedding, n)
        lexical_hits = lexical.search(query, n)

        chunks_by_id = {hit.chunk.id: hit.chunk for hit in (*vector_hits, *lexical_hits)}
        fused = reciprocal_rank_fusion(
            [[hit.chunk.id for hit in vector_hits], [hit.chunk.id for hit in lexical_hits]],
            k=self._rrf_k,
        )
        return [ScoredChunk(chunks_by_id[chunk_id], score) for chunk_id, score in fused[:k]]

    async def _lexical_index(self) -> _LexicalIndex:
        async with self._lexical_lock:
            if self._lexical is not None:
                return self._lexical
            chunks = await self._vector_store.all_chunks()
            index = _LexicalIndex(chunks, self._tokenize)
            if chunks:  # never cache an empty corpus; the index may be built later
                self._lexical = index
            return index
