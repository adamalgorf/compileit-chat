"""Composition root: the only place where adapters are bound to ports."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import cached_property
from typing import TYPE_CHECKING

from pydantic import SecretStr

from compileit_chat.application.use_cases import (
    AskQuestion,
    Authenticate,
    BuildIndex,
    ChatWithHistory,
    CreateUser,
    DeleteConversation,
    GetConversation,
    IngestWebsite,
    ListConversations,
    Login,
    Logout,
    StoreSecret,
)
from compileit_chat.application.use_cases.secrets import OPENAI_API_KEY
from compileit_chat.infrastructure.chunking.heading_chunker import (
    HeadingAwareChunker,
    tiktoken_counter,
)
from compileit_chat.infrastructure.crawling.crawler import CrawlConfig, SitemapCrawler
from compileit_chat.infrastructure.crawling.extractor import MainContentExtractor
from compileit_chat.infrastructure.llm.chat import openai_chat_model
from compileit_chat.infrastructure.llm.embeddings import LangChainEmbeddings, openai_embeddings
from compileit_chat.infrastructure.llm.tracing import enable_langsmith
from compileit_chat.infrastructure.orchestration.checkpointer import sqlite_checkpointer
from compileit_chat.infrastructure.orchestration.graph import (
    build_graph,
    mermaid_diagram,
    recursion_limit,
)
from compileit_chat.infrastructure.orchestration.nodes import AgentNodes
from compileit_chat.infrastructure.orchestration.orchestrator import LangGraphOrchestrator
from compileit_chat.infrastructure.orchestration.prompts import SYSTEM_PROMPT
from compileit_chat.infrastructure.orchestration.tools import SEARCH_TOOL, build_tools
from compileit_chat.infrastructure.persistence.database import Database
from compileit_chat.infrastructure.persistence.repositories import (
    SqlApiCallLog,
    SqlAuthSessionStore,
    SqlConversationRepository,
    SqlLoginEventLog,
    SqlUserRepository,
)
from compileit_chat.infrastructure.persistence.secret_store import (
    EncryptedSecretStore,
    generate_master_key,
)
from compileit_chat.infrastructure.retrieval.hybrid_retriever import HybridRetriever
from compileit_chat.infrastructure.retrieval.tokenizer import SwedishTokenizer
from compileit_chat.infrastructure.security import Argon2PasswordHasher, SystemClock
from compileit_chat.infrastructure.storage.jsonl_document_store import JsonlDocumentStore
from compileit_chat.infrastructure.vectorstore.chroma_store import ChromaVectorStore

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from langgraph.checkpoint.base import BaseCheckpointSaver

    from compileit_chat.config import Settings


logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """A required setting is missing."""


@dataclass(frozen=True, slots=True)
class AppUseCases:
    """Everything the HTTP API needs, built once per process."""

    chat: ChatWithHistory
    list_conversations: ListConversations
    get_conversation: GetConversation
    delete_conversation: DeleteConversation
    login: Login
    logout: Logout
    authenticate: Authenticate


class Container:
    """Builds each adapter once, on first use, so commands only pay for what they need."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._stored_openai_key: SecretStr | None = None
        if settings.langsmith_tracing:
            if settings.langsmith_api_key is None:
                raise ConfigurationError(
                    "LANGSMITH_TRACING is on but LANGSMITH_API_KEY is not set."
                )
            enable_langsmith(settings.langsmith_api_key, settings.langsmith_project)

    # --- use cases -----------------------------------------------------------------------

    def ingest_website(self) -> IngestWebsite:
        return IngestWebsite(self.crawler, MainContentExtractor(), self.document_store)

    def build_index(self) -> BuildIndex:
        return BuildIndex(self.document_store, self.chunker, self.embeddings, self.vector_store)

    @asynccontextmanager
    async def use_cases(self) -> AsyncIterator[AppUseCases]:
        """The API's use cases, with the agent's conversation store open for the block's
        lifetime. Call `start()` first."""
        conversations = SqlConversationRepository(self.database)
        clock = SystemClock()
        async with self.orchestrator() as orchestrator:
            # The orchestrator is both the ChatAgentPort and the agent-memory store.
            yield AppUseCases(
                chat=ChatWithHistory(
                    AskQuestion(orchestrator), conversations, SqlApiCallLog(self.database), clock
                ),
                list_conversations=ListConversations(conversations),
                get_conversation=GetConversation(conversations),
                delete_conversation=DeleteConversation(conversations, orchestrator),
                login=Login(
                    self.users,
                    self.password_hasher,
                    self.auth_sessions,
                    SqlLoginEventLog(self.database),
                    clock,
                    session_ttl=timedelta(hours=self.settings.auth_session_hours),
                ),
                logout=Logout(self.auth_sessions),
                authenticate=Authenticate(self.auth_sessions, self.users, clock),
            )

    def create_user(self) -> CreateUser:
        return CreateUser(self.users, self.password_hasher, SystemClock())

    def store_secret(self) -> StoreSecret:
        return StoreSecret(self.secret_store)

    @asynccontextmanager
    async def orchestrator(self) -> AsyncIterator[LangGraphOrchestrator]:
        """The agent with its SQLite conversation store open. The eval harness wraps it."""
        async with sqlite_checkpointer(self.settings.checkpoint_db) as checkpointer:
            yield self._orchestrator(checkpointer)

    async def start(self) -> None:
        """Bring the database schema up to date and load secrets stored in it.

        The OpenAI key is read from the encrypted secret store when a master key is
        configured; the OPENAI_API_KEY environment variable is the fallback.
        """
        await self.database.upgrade()
        if self.settings.secrets_master_key is not None:
            stored = await self.secret_store.get(OPENAI_API_KEY)
            self._stored_openai_key = SecretStr(stored) if stored else None
        source = "database" if self._stored_openai_key else "environment"
        logger.info("OpenAI API key source: %s", source)

    async def stop(self) -> None:
        await self.database.dispose()

    async def prepare(self) -> None:
        """API startup: `start()`, then build the search index from the snapshot if missing."""
        await self.start()
        report = await self.build_index().ensure_built()
        if report is not None:
            logger.info(
                "Built search index on first start",
                extra={"documents": report.documents, "chunks": report.chunks},
            )

    @staticmethod
    def new_master_key() -> str:
        """A fresh SECRETS_MASTER_KEY (Fernet key)."""
        return generate_master_key()

    def orchestration_diagram(self) -> str:
        """Mermaid source of the agent graph, generated from code (for the docs)."""
        return mermaid_diagram(self.settings.agent_max_tool_iterations)

    # --- adapters ------------------------------------------------------------------------

    @cached_property
    def database(self) -> Database:
        return Database(self.settings.effective_database_url)

    @cached_property
    def users(self) -> SqlUserRepository:
        return SqlUserRepository(self.database)

    @cached_property
    def auth_sessions(self) -> SqlAuthSessionStore:
        return SqlAuthSessionStore(self.database)

    @cached_property
    def password_hasher(self) -> Argon2PasswordHasher:
        return Argon2PasswordHasher()

    @cached_property
    def secret_store(self) -> EncryptedSecretStore:
        key = self.settings.secrets_master_key
        if key is None or not key.get_secret_value():
            raise ConfigurationError(
                "SECRETS_MASTER_KEY is not set. Generate one with `compileit-chat new-master-key`."
            )
        return EncryptedSecretStore(self.database, key)

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
            model=model.bind_tools(tools),
            grounding_model=model.bind_tools(tools, tool_choice=SEARCH_TOOL),
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
            max_history_messages=s.history_max_messages,
        )
        return LangGraphOrchestrator(
            build_graph(nodes, s.agent_max_tool_iterations, checkpointer),
            checkpointer,
            recursion_limit=recursion_limit(s.agent_max_tool_iterations),
            timeout_seconds=s.agent_timeout_seconds,
        )

    def _openai_api_key(self) -> SecretStr:
        key = self._stored_openai_key or self.settings.openai_api_key
        if key is None or not key.get_secret_value():
            raise ConfigurationError(
                "No OpenAI API key: store it with `compileit-chat set-secret openai_api_key` "
                "(requires SECRETS_MASTER_KEY), or set OPENAI_API_KEY."
            )
        return key
