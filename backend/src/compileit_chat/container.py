"""Composition root: the only place where adapters are bound to ports."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from compileit_chat.application.use_cases import BuildIndex, IngestWebsite
from compileit_chat.infrastructure.chunking.heading_chunker import (
    HeadingAwareChunker,
    tiktoken_counter,
)
from compileit_chat.infrastructure.crawling.crawler import CrawlConfig, SitemapCrawler
from compileit_chat.infrastructure.crawling.extractor import MainContentExtractor
from compileit_chat.infrastructure.llm.embeddings import LangChainEmbeddings, openai_embeddings
from compileit_chat.infrastructure.retrieval.hybrid_retriever import HybridRetriever
from compileit_chat.infrastructure.retrieval.tokenizer import SwedishTokenizer
from compileit_chat.infrastructure.storage.jsonl_document_store import JsonlDocumentStore
from compileit_chat.infrastructure.vectorstore.chroma_store import ChromaVectorStore

if TYPE_CHECKING:
    from pydantic import SecretStr

    from compileit_chat.config import Settings


class ConfigurationError(Exception):
    """A required setting is missing."""


class Container:
    """Builds each adapter once, on first use, so commands only pay for what they need."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # --- use cases -----------------------------------------------------------------------

    def ingest_website(self) -> IngestWebsite:
        return IngestWebsite(self.crawler, MainContentExtractor(), self.document_store)

    def build_index(self) -> BuildIndex:
        return BuildIndex(self.document_store, self.chunker, self.embeddings, self.vector_store)

    # --- adapters ------------------------------------------------------------------------

    @cached_property
    def crawler(self) -> SitemapCrawler:
        s = self.settings
        return SitemapCrawler(
            CrawlConfig(
                site_url=s.site_url,
                user_agent=s.crawl_user_agent,
                max_pages=s.crawl_max_pages,
                max_depth=s.crawl_max_depth,
                concurrency=s.crawl_concurrency,
                timeout_seconds=s.crawl_timeout_seconds,
                exclude_patterns=tuple(s.crawl_exclude_patterns),
            )
        )

    @cached_property
    def chunker(self) -> HeadingAwareChunker:
        s = self.settings
        return HeadingAwareChunker(
            tiktoken_counter(),
            target_tokens=s.chunk_target_tokens,
            max_tokens=s.chunk_max_tokens,
            overlap_tokens=s.chunk_overlap_tokens,
        )

    @cached_property
    def document_store(self) -> JsonlDocumentStore:
        return JsonlDocumentStore(self.settings.snapshot_path)

    @cached_property
    def vector_store(self) -> ChromaVectorStore:
        return ChromaVectorStore(self.settings.chroma_dir)

    @cached_property
    def retriever(self) -> HybridRetriever:
        return HybridRetriever(
            self.embeddings,
            self.vector_store,
            SwedishTokenizer(),
            vector_candidates=self.settings.retrieval_vector_candidates,
            lexical_candidates=self.settings.retrieval_lexical_candidates,
            rrf_k=self.settings.rrf_k,
        )

    @cached_property
    def embeddings(self) -> LangChainEmbeddings:
        return LangChainEmbeddings(
            openai_embeddings(self.settings.embedding_model, self._openai_api_key())
        )

    def _openai_api_key(self) -> SecretStr:
        key = self.settings.openai_api_key
        if key is None or not key.get_secret_value():
            raise ConfigurationError("OPENAI_API_KEY is not set. Copy .env.example to .env.")
        return key
