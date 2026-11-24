"""Saved conversations and the log of answered API calls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.domain.documents import SourceRef

TITLE_LENGTH = 60


class Role(StrEnum):
    """Who wrote a saved message."""

    USER = "user"
    ASSISTANT = "assistant"


class CallStatus(StrEnum):
    """How a chat request ended."""

    DONE = "done"  # answered
    ERROR = "error"  # the agent failed; the user saw an error message
    STOPPED = "stopped"  # the client disconnected (stop button, closed tab)


@dataclass(frozen=True, slots=True)
class Conversation:
    """A chat session owned by one user. Its id is the session id the agent remembers."""

    id: SessionId
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredMessage:
    """One saved message of a conversation, as shown in the history."""

    role: Role
    content: str
    created_at: datetime
    sources: tuple[SourceRef, ...] = ()
    status: CallStatus | None = None  # assistant messages only


@dataclass(frozen=True, slots=True)
class ApiCallRecord:
    """One answered `/api/chat` call, for auditing and quality follow-up."""

    user_id: str
    conversation_id: SessionId
    question: str
    answer: str
    sources: tuple[SourceRef, ...]
    tools: tuple[str, ...]  # e.g. "search_website: AI-tjänster"
    status: CallStatus
    first_token_ms: int | None
    total_ms: int
    created_at: datetime


def conversation_title(question: Question) -> str:
    """The first question, shortened at a word boundary, names the conversation."""
    text = " ".join(question.text.split())
    if len(text) <= TITLE_LENGTH:
        return text
    cut = text[:TITLE_LENGTH].rsplit(" ", 1)[0] or text[:TITLE_LENGTH]
    return f"{cut}…"
