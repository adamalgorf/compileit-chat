"""Builds the real LangGraph agent around a scripted model and in-memory content."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from compileit_chat.domain.documents import ScoredChunk
from compileit_chat.infrastructure.agent.agent import LangGraphChatAgent
from compileit_chat.infrastructure.agent.graph import build_agent_graph
from compileit_chat.infrastructure.agent.tools import build_tools
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


def make_agent(
    model: ScriptedChatModel,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    max_steps: int = 12,
) -> LangGraphChatAgent:
    saver = checkpointer or InMemorySaver()
    tools = build_tools(StaticRetriever(CONTACT_HITS), InMemoryDocumentStore([CONTACT]))
    graph = build_agent_graph(model, tools, "SYSTEM", saver, max_history_messages=20)
    return LangGraphChatAgent(graph, saver, max_steps=max_steps, timeout_seconds=10)


def contact_turn() -> list[AIMessage]:
    """Model replies for one turn: search for 'kontakt', then answer citing /kontakt."""
    return [tool_call("search_website", query="kontakt"), AIMessage(CONTACT_ANSWER)]
