"""Answer a question in a session, as a stream of events."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.errors import AgentError
from compileit_chat.domain.sources import cited_sources

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import ChatEvent
    from compileit_chat.application.ports import ChatAgentPort
    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.domain.documents import SourceRef

logger = logging.getLogger(__name__)

AGENT_ERROR_MESSAGE = (
    "Något gick fel när jag skulle ta fram ett svar. Försök gärna igen om en stund."
)


class AskQuestion:
    """Stream the agent's answer, then the sources it cited, then `DoneEvent`.

    Contract for clients: zero or more `TokenEvent`/`ToolCallEvent`, followed by either
    `SourcesEvent` + `DoneEvent`, or a single `ErrorEvent`.
    """

    def __init__(self, agent: ChatAgentPort) -> None:
        self._agent = agent

    async def execute(self, session_id: SessionId, question: Question) -> AsyncIterator[ChatEvent]:
        """Run one turn. The agent is only known through `ChatAgentPort`, never LangGraph."""
        answer_parts: list[str] = []  # the answer so far, to see which sources it cites
        retrieved: list[SourceRef] = []  # every page the tools returned this turn
        try:
            async for event in self._agent.stream(session_id, question):
                match event:
                    case TokenEvent(text=text):
                        answer_parts.append(text)
                        yield event
                    case ToolCallEvent():
                        yield event
                    case RetrievalEvent(sources=sources):
                        # Internal: not sent to the client. Searches return pages the answer
                        # may not use, and those should not appear as sources.
                        retrieved.extend(sources)
        except AgentError:
            # The adapter has logged the cause; the user only gets a friendly Swedish message.
            logger.exception("Agent failed", extra={"session_id": str(session_id)})
            yield ErrorEvent(message=AGENT_ERROR_MESSAGE)
            return

        # Show only the retrieved pages the answer actually links to.
        yield SourcesEvent(sources=cited_sources("".join(answer_parts), retrieved))
        yield DoneEvent()
