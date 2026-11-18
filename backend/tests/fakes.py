"""In-memory port implementations for tests. No network, no frameworks."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from compileit_chat.application.errors import AgentError, UserExistsError
from compileit_chat.domain.documents import Chunk, Document, FetchedPage, Language, ScoredChunk

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping, Sequence

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.accounts import User, Username
    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.domain.history import ApiCallRecord, Conversation, StoredMessage


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
        scored = [
            ScoredChunk(chunk, _cosine(embedding, vector))
            for chunk, vector in zip(self.chunks, self.embeddings, strict=True)
        ]
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:k]

    async def all_chunks(self) -> list[Chunk]:
        return list(self.chunks)


class KeywordEmbeddings:
    """Embeds text as keyword-presence vectors: deterministic 'semantics' for retrieval tests."""

    def __init__(self, keywords: Sequence[str]) -> None:
        self._keywords = keywords

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        lowered = text.casefold()
        return [1.0 if keyword in lowered else 0.0 for keyword in self._keywords] + [0.01]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class StaticRetriever:
    """Returns the same hits for every query; records the queries."""

    def __init__(self, hits: Sequence[ScoredChunk]) -> None:
        self._hits = hits
        self.queries: list[str] = []

    async def search(self, query: str, k: int) -> list[ScoredChunk]:
        self.queries.append(query)
        return list(self._hits[:k])


# --- accounts, history, audit ------------------------------------------------------------


class FixedClock:
    def __init__(self, now: datetime = NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


class PlainTextHasher:
    """Fast, deterministic stand-in for Argon2 (tests only)."""

    def hash(self, password: str) -> str:
        return f"hashed:{password}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == f"hashed:{password}"


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def get(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    async def get_by_username(self, username: Username) -> User | None:
        return next((u for u in self.users.values() if u.username == username), None)

    async def add(self, user: User) -> None:
        if await self.get_by_username(user.username):
            raise UserExistsError(user.username.value)
        self.users[user.id] = user


class InMemoryAuthSessions:
    def __init__(self) -> None:
        self.sessions: dict[str, tuple[str, datetime]] = {}

    async def create(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        self.sessions[token_hash] = (user_id, expires_at)

    async def user_id_for(self, token_hash: str, now: datetime) -> str | None:
        entry = self.sessions.get(token_hash)
        return entry[0] if entry and entry[1] > now else None

    async def delete(self, token_hash: str) -> None:
        self.sessions.pop(token_hash, None)


class LoginEventRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, bool, str | None]] = []

    async def record(
        self, username: str, succeeded: bool, client: str | None, at: datetime
    ) -> None:
        self.events.append((username, succeeded, client))


class InMemoryConversations:
    def __init__(self) -> None:
        self.conversations: dict[str, Conversation] = {}
        self.stored: dict[str, list[StoredMessage]] = {}

    async def get(self, conversation_id: SessionId) -> Conversation | None:
        return self.conversations.get(str(conversation_id))

    async def create(self, conversation: Conversation) -> None:
        self.conversations[str(conversation.id)] = conversation
        self.stored[str(conversation.id)] = []

    async def list_for_user(self, user_id: str) -> list[Conversation]:
        mine = [c for c in self.conversations.values() if c.user_id == user_id]
        return sorted(mine, key=lambda c: c.updated_at, reverse=True)

    async def messages(self, conversation_id: SessionId) -> list[StoredMessage]:
        return list(self.stored.get(str(conversation_id), []))

    async def add_message(self, conversation_id: SessionId, message: StoredMessage) -> None:
        self.stored[str(conversation_id)].append(message)

    async def delete(self, conversation_id: SessionId) -> None:
        self.conversations.pop(str(conversation_id), None)
        self.stored.pop(str(conversation_id), None)


class ApiCallRecorder:
    def __init__(self) -> None:
        self.calls: list[ApiCallRecord] = []

    async def record(self, call: ApiCallRecord) -> None:
        self.calls.append(call)


class InMemorySecretStore:
    def __init__(self) -> None:
        self.secrets: dict[str, str] = {}

    async def get(self, name: str) -> str | None:
        return self.secrets.get(name)

    async def put(self, name: str, value: str) -> None:
        self.secrets[name] = value
