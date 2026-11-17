"""Events streamed while answering a question.

These are the application's own types: the API serialises them to SSE, and agent adapters
translate framework callbacks into them, so no LangChain type crosses a layer boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compileit_chat.domain.documents import SourceRef


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """A text delta of the answer."""

    text: str


@dataclass(frozen=True, slots=True)
class ToolCallEvent:
    """The agent started a tool, e.g. a website search. Lets the UI show what it is doing."""

    tool: str
    query: str | None = None


@dataclass(frozen=True, slots=True)
class RetrievalEvent:
    """Pages a tool returned to the agent. Internal: consumed by `AskQuestion`, never sent."""

    sources: tuple[SourceRef, ...]


@dataclass(frozen=True, slots=True)
class SourcesEvent:
    """The de-duplicated pages the final answer cites."""

    sources: tuple[SourceRef, ...]


@dataclass(frozen=True, slots=True)
class DoneEvent:
    """The answer is complete."""


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """The answer failed. `message` is user-facing (Swedish)."""

    message: str


type AgentEvent = TokenEvent | ToolCallEvent | RetrievalEvent
"""What a `ChatAgentPort` adapter emits."""

type ChatEvent = TokenEvent | ToolCallEvent | SourcesEvent | DoneEvent | ErrorEvent
"""What clients receive."""
