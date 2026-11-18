"""`ChatAgentPort` + `ConversationStorePort` adapter over the compiled LangGraph agent.

Translates LangGraph's stream into the application's own events and framework exceptions
into `AgentError`, so nothing LangChain-specific leaks past this module.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from compileit_chat.application.dto import RetrievalEvent, TokenEvent, ToolCallEvent
from compileit_chat.application.errors import AgentError
from compileit_chat.domain.documents import SourceRef
from compileit_chat.infrastructure.agent.graph import AGENT_NODE, TOOLS_NODE

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from langchain_core.runnables import RunnableConfig
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph import MessagesState
    from langgraph.graph.state import CompiledStateGraph

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.conversation import Question, SessionId

logger = logging.getLogger(__name__)

# The tool argument shown to users while a tool runs ("Söker på webbplatsen: '…'").
_DISPLAY_ARGUMENT = {"search_website": "query", "get_page": "url_or_title"}


class LangGraphChatAgent:
    def __init__(
        self,
        graph: CompiledStateGraph[MessagesState],
        checkpointer: BaseCheckpointSaver[str],
        *,
        max_steps: int,
        timeout_seconds: float,
    ) -> None:
        self._graph = graph
        self._checkpointer = checkpointer
        self._max_steps = max_steps
        self._timeout_seconds = timeout_seconds

    async def stream(self, session_id: SessionId, question: Question) -> AsyncIterator[AgentEvent]:
        config: RunnableConfig = {
            "configurable": {"thread_id": str(session_id)},
            "recursion_limit": self._max_steps,
        }
        inputs: MessagesState = {"messages": [HumanMessage(question.text)]}
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async for mode, payload in self._graph.astream(
                    inputs, config, stream_mode=["messages", "updates"]
                ):
                    for event in _events(mode, payload):
                        yield event
        except Exception as error:
            # Boundary translation: provider errors, timeouts and GraphRecursionError all
            # mean "no answer"; the use case turns that into a user-facing message.
            logger.warning("Agent run failed: %r", error, extra={"session_id": str(session_id)})
            raise AgentError(type(error).__name__) from error

    async def reset(self, session_id: SessionId) -> None:
        await self._checkpointer.adelete_thread(str(session_id))


def _events(mode: str, payload: Any) -> Iterator[AgentEvent]:
    if mode == "messages":
        chunk, metadata = payload
        if (
            metadata.get("langgraph_node") == AGENT_NODE
            and isinstance(chunk, AIMessageChunk)
            and chunk.text
        ):
            yield TokenEvent(chunk.text)
        return

    for node, update in (payload or {}).items():
        for message in (update or {}).get("messages", []):
            if node == AGENT_NODE and isinstance(message, AIMessage):
                for call in message.tool_calls:
                    argument = call["args"].get(_DISPLAY_ARGUMENT.get(call["name"], ""))
                    yield ToolCallEvent(tool=call["name"], query=argument)
            elif node == TOOLS_NODE and isinstance(message, ToolMessage) and message.artifact:
                yield RetrievalEvent(
                    sources=tuple(SourceRef(s["title"], s["url"]) for s in message.artifact)
                )
