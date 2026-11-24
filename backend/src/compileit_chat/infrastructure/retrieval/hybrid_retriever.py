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
    """BM25 over the chunks, returning chunks instead of BM25's document indexes."""

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
    """Vector search is the backbone; BM25 contributes only its few strongest hits.

    Measured on this corpus (ADR-0003): fusing BM25's full top 20 lets chunks that merely
    share generic words ("typer", "jobbar") outvote the best vector hit, through RRF's
    agreement bonus. Its top 3 keeps the exact-term wins without that noise.

    The BM25 index is built from the vector store on first search and then cached; the
    corpus only changes on re-ingestion, which happens offline, so restart to pick it up.
    """

    def __init__(
        self,
        embeddings: EmbeddingPort,
        vector_store: VectorStorePort,
        tokenize: Tokenizer,
        vector_candidates: int = 20,
        lexical_candidates: int = 3,
        rrf_k: int = 60,
    ) -> None:
        self._embeddings = embeddings
        self._vector_store = vector_store
        self._tokenize = tokenize
        self._vector_candidates = vector_candidates
        self._lexical_candidates = lexical_candidates
        self._rrf_k = rrf_k
        self._lexical: _LexicalIndex | None = None
        self._lexical_lock = asyncio.Lock()

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        """The `k` best chunks for the query, ranked by fused score."""
        lexical = await self._lexical_index()
        # Two independent rankings: a wide vector candidate list, and BM25's best few.
        embedding = await self._embeddings.embed_query(query)
        vector_hits = await self._vector_store.search(embedding, max(k, self._vector_candidates))
        lexical_hits = lexical.search(query, self._lexical_candidates)

        # RRF merges by rank (ids only); look the chunks up again afterwards.
        chunks_by_id = {hit.chunk.id: hit.chunk for hit in (*vector_hits, *lexical_hits)}
        fused = reciprocal_rank_fusion(
            [[hit.chunk.id for hit in vector_hits], [hit.chunk.id for hit in lexical_hits]],
            k=self._rrf_k,
        )
        return [ScoredChunk(chunks_by_id[chunk_id], score) for chunk_id, score in fused[:k]]

    async def _lexical_index(self) -> _LexicalIndex:
        """Build the BM25 index once; the lock stops concurrent first requests building twice."""
        async with self._lexical_lock:
            if self._lexical is not None:
                return self._lexical
            chunks = await self._vector_store.all_chunks()
            index = _LexicalIndex(chunks, self._tokenize)
            if chunks:  # never cache an empty corpus; the index may be built later
                self._lexical = index
            return index
