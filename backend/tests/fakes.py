"""In-memory port implementations for tests. No network, no frameworks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from compileit_chat.application.errors import AgentError
from compileit_chat.domain.documents import Chunk, Document, FetchedPage, Language

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.domain.documents import ScoredChunk

NOW = datetime(2026, 11, 17, tzinfo=UTC)


def make_document(url: str, text: str = "Innehåll", title: str = "Sida") -> Document:
    return Document(url=url, title=title, text=text, lang=Language.SWEDISH, crawled_at=NOW)


# --- chat --------------------------------------------------------------------------------


class ScriptedAgent:
    """Replays a fixed event script; optionally fails after it, like a mid-stream timeout."""

    def __init__(self, events: Sequence[AgentEvent], *, fail: bool = False) -> None:
        self._events = events
        self._fail = fail
        self.calls: list[tuple[SessionId, Question]] = []

    async def stream(self, session_id: SessionId, question: Question) -> AsyncIterator[AgentEvent]:
        self.calls.append((session_id, question))
        for event in self._events:
            yield event
        if self._fail:
            raise AgentError("scripted failure")


class InMemoryConversationStore:
    def __init__(self, sessions: set[SessionId] | None = None) -> None:
        self.sessions: set[SessionId] = sessions or set()

    async def reset(self, session_id: SessionId) -> None:
        self.sessions.discard(session_id)


# --- ingestion ---------------------------------------------------------------------------


class FakeCrawler:
    def __init__(self, urls: Sequence[str]) -> None:
        self._urls = urls

    async def crawl(self) -> AsyncIterator[FetchedPage]:
        for url in self._urls:
            yield FetchedPage(url=url, html="<html></html>", fetched_at=NOW)


class FakeExtractor:
    """Returns the prepared document for a URL, or None (= no content) if there is none."""

    def __init__(self, documents: Mapping[str, Document]) -> None:
        self._documents = documents

    def extract(self, page: FetchedPage) -> Document | None:
        return self._documents.get(page.url)


class InMemoryDocumentStore:
    def __init__(self, documents: Sequence[Document] = ()) -> None:
        self.documents = list(documents)

    async def replace_all(self, documents: Sequence[Document]) -> None:
        self.documents = list(documents)

    async def get(self, url: str) -> Document | None:
        return next((d for d in self.documents if d.url == url), None)

    async def list_all(self) -> list[Document]:
        return list(self.documents)


class ParagraphChunker:
    """One chunk per blank-line-separated paragraph."""

    def split(self, document: Document) -> list[Chunk]:
        return [
            Chunk(
                document_url=document.url,
                title=document.title,
                section_heading=None,
                text=paragraph,
                lang=document.lang,
                crawled_at=document.crawled_at,
                position=position,
            )
            for position, paragraph in enumerate(document.text.split("\n\n"))
        ]


class LengthEmbeddings:
    """A 2-d 'embedding' derived from text length; enough to check plumbing."""

    def __init__(self) -> None:
        self.embedded: list[str] = []

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return [[float(len(text)), 1.0] for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return [float(len(text)), 1.0]


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.chunks: list[Chunk] = []
        self.embeddings: list[Sequence[float]] = []

    async def replace_all(
        self, chunks: Sequence[Chunk], embeddings: Sequence[Sequence[float]]
    ) -> None:
        self.chunks, self.embeddings = list(chunks), list(embeddings)

    async def count(self) -> int:
        return len(self.chunks)

    async def search(self, embedding: Sequence[float], k: int) -> list[ScoredChunk]:
        raise NotImplementedError  # not needed until retrieval tests

    async def all_chunks(self) -> list[Chunk]:
        return list(self.chunks)
