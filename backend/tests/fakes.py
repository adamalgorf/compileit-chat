"""In-memory port implementations for tests. No network, no frameworks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from compileit_chat.application.errors import AgentError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.conversation import Question, SessionId


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
