"""Ports for answering questions within a conversation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.conversation import Question, SessionId


class ChatAgentPort(Protocol):
    def stream(self, session_id: SessionId, question: Question) -> AsyncIterator[AgentEvent]:
        """Answer `question` in the context of earlier turns in the same session.

        The adapter owns conversation memory for the session. Raises `AgentError` on failure.
        """
        ...


class ConversationStorePort(Protocol):
    async def reset(self, session_id: SessionId) -> None:
        """Forget all turns of the session. Resetting an unknown session is a no-op."""
        ...
