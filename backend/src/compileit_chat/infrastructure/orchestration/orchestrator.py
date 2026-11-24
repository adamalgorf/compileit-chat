"""`LangGraphOrchestrator`: runs the compiled graph for one turn of a session.

Implements `ChatAgentPort` (and `ConversationStorePort` for reset). It owns the agent's
control flow at runtime: thread selection, step cap, timeout and error translation. It
maps LangGraph's `astream_events` to application events, so no LangChain type reaches the
use case or the API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessageChunk

from compileit_chat.application.dto import RetrievalEvent, TokenEvent, ToolCallEvent
from compileit_chat.application.errors import AgentError
from compileit_chat.domain.documents import SourceRef
from compileit_chat.infrastructure.orchestration.graph import (
    CALL_MODEL,
    COLLECT_SOURCES,
    HANDLE_FALLBACK,
)
from compileit_chat.infrastructure.orchestration.state import new_turn

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from langchain_core.runnables import RunnableConfig
    from langchain_core.runnables.schema import StreamEvent
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.infrastructure.orchestration.state import AgentState

logger = logging.getLogger(__name__)

# The tool argument shown to users while a tool runs ("Söker på webbplatsen: '…'").
_DISPLAY_ARGUMENT = {"search_website": "query", "get_page": "url_or_title"}


class LangGraphOrchestrator:
    """Adapter behind `ChatAgentPort`: one `stream` call is one turn of a conversation."""

    def __init__(
        self,
        graph: CompiledStateGraph[AgentState],
        checkpointer: BaseCheckpointSaver[str],
        *,
        recursion_limit: int,
        timeout_seconds: float,
    ) -> None:
        self._graph = graph
        self._checkpointer = checkpointer
        self._recursion_limit = recursion_limit
        self._timeout_seconds = timeout_seconds

    async def stream(self, session_id: SessionId, question: Question) -> AsyncIterator[AgentEvent]:
        """Run the graph for one question and yield application events as they happen.

        The session id is the LangGraph thread id: the checkpointer loads that session's
        earlier messages, so the model sees the conversation so far.
        """
        config: RunnableConfig = {
            "configurable": {"thread_id": str(session_id)},
            "recursion_limit": self._recursion_limit,
        }
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async for event in self._graph.astream_events(
                    new_turn(question.text), config, version="v2"
                ):
                    for mapped in _to_application_events(event):
                        yield mapped
        except Exception as error:
            # Boundary translation: provider errors, timeouts and the recursion backstop all
            # mean "no answer"; the use case turns that into a user-facing message.
            logger.warning(
                "Agent run failed: %r", error, exc_info=True, extra={"session_id": str(session_id)}
            )
            raise AgentError(type(error).__name__) from error

    async def reset(self, session_id: SessionId) -> None:
        """Forget a session: delete its checkpointed conversation."""
        await self._checkpointer.adelete_thread(str(session_id))


def _to_application_events(event: StreamEvent) -> Iterator[AgentEvent]:
    """Translate one LangGraph event into zero or more application events.

    LangGraph emits many events per turn; only four matter to the user: answer tokens,
    a tool starting, the sources found, and the fallback answer. Everything else is dropped.
    """
    kind, name = event["event"], event["name"]
    node = event.get("metadata", {}).get("langgraph_node")
    data = event.get("data", {})

    # Tokens: only from the answering node. Text the model writes alongside tool calls is
    # also a stream of tokens, and is shown as part of the answer.
    if kind == "on_chat_model_stream" and node == CALL_MODEL:
        chunk = data.get("chunk")
        if isinstance(chunk, AIMessageChunk) and chunk.text:
            yield TokenEvent(chunk.text)
    elif kind == "on_tool_start":
        # Drives the "Söker på webbplatsen: '…'" indicator in the UI.
        arguments = data.get("input") or {}
        yield ToolCallEvent(tool=name, query=arguments.get(_DISPLAY_ARGUMENT.get(name, "")))
    elif kind == "on_chain_end" and name == node == COLLECT_SOURCES:
        # The node's output holds every source of the turn so far, deduplicated by URL.
        sources = data["output"]["sources"]
        yield RetrievalEvent(sources=tuple(SourceRef(s["title"], s["url"]) for s in sources))
    elif kind == "on_chain_end" and name == node == HANDLE_FALLBACK:
        # Not produced by the model, so it is not streamed token by token; send it whole.
        yield TokenEvent(data["output"]["messages"][-1].text)
