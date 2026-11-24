"""`EmbeddingPort` adapter over any LangChain `Embeddings`, plus the OpenAI factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_openai import OpenAIEmbeddings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from langchain_core.embeddings import Embeddings
    from pydantic import SecretStr


class LangChainEmbeddings:
    """`EmbeddingPort` adapter over any LangChain embeddings model."""

    def __init__(self, embeddings: Embeddings) -> None:
        self._embeddings = embeddings

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return await self._embeddings.aembed_documents(list(texts))

    async def embed_query(self, text: str) -> list[float]:
        return await self._embeddings.aembed_query(text)


def openai_embeddings(model: str, api_key: SecretStr) -> Embeddings:
    """OpenAI embeddings, retried on transient API errors."""
    return OpenAIEmbeddings(model=model, api_key=api_key, max_retries=3)
