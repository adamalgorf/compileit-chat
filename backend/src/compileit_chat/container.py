"""Composition root: the only place where adapters are bound to ports."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from compileit_chat.application.use_cases import (
    AskQuestion,
    BuildIndex,
    IngestWebsite,
    ResetConversation,
)
from compileit_chat.infrastructure.chunking.heading_chunker import (
    HeadingAwareChunker,
    tiktoken_counter,
)
from compileit_chat.infrastructure.crawling.crawler import CrawlConfig, SitemapCrawler
from compileit_chat.infrastructure.crawling.extractor import MainContentExtractor
from compileit_chat.infrastructure.llm.chat import openai_chat_model
from compileit_chat.infrastructure.llm.embeddings import LangChainEmbeddings, openai_embeddings
from compileit_chat.infrastructure.orchestration.checkpointer import sqlite_checkpointer
from compileit_chat.infrastructure.orchestration.graph import (
    build_graph,
    mermaid_diagram,
    recursion_limit,
)
from compileit_chat.infrastructure.orchestration.nodes import AgentNodes
from compileit_chat.infrastructure.orchestration.orchestrator import LangGraphOrchestrator
from compileit_chat.infrastructure.orchestration.prompts import SYSTEM_PROMPT
from compileit_chat.infrastructure.orchestration.tools import build_tools
from compileit_chat.infrastructure.retrieval.hybrid_retriever import HybridRetriever
from compileit_chat.infrastructure.retrieval.tokenizer import SwedishTokenizer
from compileit_chat.infrastructure.storage.jsonl_document_store import JsonlDocumentStore
from compileit_chat.infrastructure.vectorstore.chroma_store import ChromaVectorStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langgraph.checkpoint.base import BaseCheckpointSaver
    from pydantic import SecretStr

    from compileit_chat.config import Settings


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """A required setting is missing."""


@dataclass(frozen=True, slots=True)
class ChatUseCases:
    ask: AskQuestion
    reset: ResetConversation


class Container:
    """Builds each adapter once, on first use, so commands only pay for what they need."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # --- use cases -----------------------------------------------------------------------

    def ingest_website(self) -> IngestWebsite:
        return IngestWebsite(self.crawler, MainContentExtractor(), self.document_store)

    def build_index(self) -> BuildIndex:
        return BuildIndex(self.document_store, self.chunker, self.embeddings, self.vector_store)

    @asynccontextmanager
    async def chat(self) -> AsyncIterator[ChatUseCases]:
        """Chat use cases, backed by a SQLite conversation store open for the block's lifetime.

        Sessions are LangGraph threads, so they survive restarts.
        """
        async with self.orchestrator() as orchestrator:
            # The orchestrator is both the ChatAgentPort and the ConversationStorePort.
            yield ChatUseCases(ask=AskQuestion(orchestrator), reset=ResetConversation(orchestrator))

    @asynccontextmanager
    async def orchestrator(self) -> AsyncIterator[LangGraphOrchestrator]:
        """The agent with its SQLite conversation store open. The eval harness wraps it."""
        async with sqlite_checkpointer(self.settings.checkpoint_db) as checkpointer:
            yield self._orchestrator(checkpointer)

    async def prepare(self) -> None:
        """Startup work for the API: build the search index from the snapshot if missing."""
        report = await self.build_index().ensure_built()
        if report is not None:
            logger.info(
                "Built search index on first start",
                extra={"documents": report.documents, "chunks": report.chunks},
            )

    def orchestration_diagram(self) -> str:
        """Mermaid source of the agent graph, generated from code (for the docs)."""
        return mermaid_diagram(self.settings.agent_max_tool_iterations)

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

    def _orchestrator(self, checkpointer: BaseCheckpointSaver[str]) -> LangGraphOrchestrator:
        s = self.settings
        tools = build_tools(self.retriever, self.document_store)
        model = openai_chat_model(
            s.chat_model, self._openai_api_key(), s.chat_temperature, s.llm_timeout_seconds
        )
        nodes = AgentNodes(
            model.bind_tools(tools),
            tools,
            SYSTEM_PROMPT,
            max_history_messages=s.history_max_messages,
        )
        return LangGraphOrchestrator(
            build_graph(nodes, s.agent_max_tool_iterations, checkpointer),
            checkpointer,
            recursion_limit=recursion_limit(s.agent_max_tool_iterations),
            timeout_seconds=s.agent_timeout_seconds,
        )

    def _openai_api_key(self) -> SecretStr:
        key = self.settings.openai_api_key
        if key is None or not key.get_secret_value():
            raise ConfigurationError("OPENAI_API_KEY is not set. Copy .env.example to .env.")
        return key
