"""Builds the real orchestration graph around a scripted model and in-memory content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from compileit_chat.domain.documents import ScoredChunk
from compileit_chat.infrastructure.orchestration.graph import build_graph, recursion_limit
from compileit_chat.infrastructure.orchestration.nodes import AgentNodes
from compileit_chat.infrastructure.orchestration.orchestrator import LangGraphOrchestrator
from compileit_chat.infrastructure.orchestration.tools import build_tools
from tests.fakes import InMemoryDocumentStore, ParagraphChunker, StaticRetriever, make_document
from tests.scripted_chat_model import tool_call

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from tests.scripted_chat_model import ScriptedChatModel

CONTACT = make_document(
    "https://compileit.com/kontakt", "Mejla hello@compileit.com.", "Kontakta oss"
)
CONTACT_HITS = [ScoredChunk(chunk, 1.0) for chunk in ParagraphChunker().split(CONTACT)]
CONTACT_ANSWER = f"Mejla hello@compileit.com, se [Kontakta oss]({CONTACT.url})."


def make_orchestrator(
    model: ScriptedChatModel,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    max_tool_iterations: int = 4,
) -> LangGraphOrchestrator:
    saver = checkpointer or InMemorySaver()
    tools = build_tools(StaticRetriever(CONTACT_HITS), InMemoryDocumentStore([CONTACT]))
    bound = model.bind_tools(tools)  # the scripted model ignores tool_choice
    nodes = AgentNodes(
        model=bound,
        grounding_model=bound,
        tools=tools,
        system_prompt="SYSTEM",
        max_history_messages=20,
    )
    return LangGraphOrchestrator(
        build_graph(nodes, max_tool_iterations, saver),
        saver,
        recursion_limit=recursion_limit(max_tool_iterations),
        timeout_seconds=10,
    )


def contact_turn() -> list[AIMessage]:
    """Model replies for one turn: search for 'kontakt', then answer citing /kontakt."""
    return [tool_call("search_website", query="kontakt"), AIMessage(CONTACT_ANSWER)]
