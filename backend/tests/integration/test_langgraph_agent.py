"""The real LangGraph graph, tools and checkpointers, driven by a scripted chat model."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from compileit_chat.application.dto import (
    DoneEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.errors import AgentError
from compileit_chat.application.use_cases import AskQuestion
from compileit_chat.domain.conversation import Question, SessionId
from compileit_chat.domain.documents import ScoredChunk, SourceRef
from compileit_chat.infrastructure.agent.agent import LangGraphChatAgent
from compileit_chat.infrastructure.agent.graph import build_agent_graph
from compileit_chat.infrastructure.agent.tools import build_tools
from tests.fakes import InMemoryDocumentStore, ParagraphChunker, StaticRetriever, make_document
from tests.scripted_chat_model import ScriptedChatModel, tool_call

if TYPE_CHECKING:
    from pathlib import Path

    from langgraph.checkpoint.base import BaseCheckpointSaver

    from compileit_chat.application.dto import AgentEvent

CONTACT = make_document(
    "https://compileit.com/kontakt", "Mejla hello@compileit.com.", "Kontakta oss"
)
CONTACT_HITS = [ScoredChunk(chunk, 1.0) for chunk in ParagraphChunker().split(CONTACT)]
SESSION = SessionId("session-0001")
ANSWER = f"Mejla hello@compileit.com, se [Kontakta oss]({CONTACT.url})."


def make_agent(
    model: ScriptedChatModel,
    checkpointer: BaseCheckpointSaver[str] | None = None,
    max_steps: int = 12,
) -> LangGraphChatAgent:
    saver = checkpointer or InMemorySaver()
    tools = build_tools(StaticRetriever(CONTACT_HITS), InMemoryDocumentStore([CONTACT]))
    graph = build_agent_graph(model, tools, "SYSTEM", saver, max_history_messages=20)
    return LangGraphChatAgent(graph, saver, max_steps=max_steps, timeout_seconds=10)


async def run(
    agent: LangGraphChatAgent, question: str, session: SessionId = SESSION
) -> list[AgentEvent]:
    return [event async for event in agent.stream(session, Question(question))]


def contact_turn() -> list[AIMessage]:
    return [tool_call("search_website", query="kontakt"), AIMessage(ANSWER)]


async def test_streams_tool_call_retrieval_and_answer_tokens() -> None:
    events = await run(
        make_agent(ScriptedChatModel(replies=contact_turn())), "Hur kontaktar man er?"
    )

    assert events[:2] == [
        ToolCallEvent(tool="search_website", query="kontakt"),
        RetrievalEvent(sources=(SourceRef("Kontakta oss", CONTACT.url),)),
    ]
    tokens = events[2:]
    assert all(isinstance(e, TokenEvent) for e in tokens)
    assert len(tokens) > 1  # streamed, not one blob
    assert "".join(e.text for e in tokens if isinstance(e, TokenEvent)) == ANSWER


async def test_model_gets_system_prompt_and_tool_results() -> None:
    model = ScriptedChatModel(replies=contact_turn())

    await run(make_agent(model), "Hur kontaktar man er?")

    second_call = model.received[1]
    assert second_call[0].content == "SYSTEM"
    assert "<källa" in str(second_call[-1].content)  # the tool result, delimited


async def test_follow_up_sees_earlier_turn_but_other_sessions_do_not() -> None:
    model = ScriptedChatModel(replies=[*contact_turn(), AIMessage("Svar 2"), AIMessage("Svar 3")])
    agent = make_agent(model)

    await run(agent, "Hur kontaktar man er?")
    await run(agent, "Berätta mer")
    await run(agent, "Hej", session=SessionId("another-session"))

    follow_up, other = model.received[2], model.received[3]
    assert [m.content for m in follow_up if isinstance(m, HumanMessage)] == [
        "Hur kontaktar man er?",
        "Berätta mer",
    ]
    assert [m.content for m in other if isinstance(m, HumanMessage)] == ["Hej"]


async def test_reset_forgets_the_session() -> None:
    model = ScriptedChatModel(replies=[AIMessage("Svar 1"), AIMessage("Svar 2")])
    agent = make_agent(model)

    await run(agent, "Fråga 1")
    await agent.reset(SESSION)
    await run(agent, "Fråga 2")

    assert [m.content for m in model.received[1] if isinstance(m, HumanMessage)] == ["Fråga 2"]


async def test_sessions_survive_a_restart_with_sqlite(tmp_path: Path) -> None:
    db = str(tmp_path / "checkpoints.sqlite3")
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        await run(make_agent(ScriptedChatModel(replies=[AIMessage("Svar 1")]), saver), "Fråga 1")

    model = ScriptedChatModel(replies=[AIMessage("Svar 2")])
    async with AsyncSqliteSaver.from_conn_string(db) as saver:  # "restarted" process
        await run(make_agent(model, saver), "Fråga 2")

    assert [m.content for m in model.received[0] if isinstance(m, HumanMessage)] == [
        "Fråga 1",
        "Fråga 2",
    ]


async def test_endless_tool_loop_is_stopped_by_the_step_limit() -> None:
    model = ScriptedChatModel(replies=[tool_call("search_website", query="x")], repeat_last=True)

    with pytest.raises(AgentError, match="GraphRecursionError"):
        await run(make_agent(model, max_steps=5), "Loopa")


async def test_provider_errors_become_agent_errors() -> None:
    model = ScriptedChatModel(replies=[], error=ConnectionError("provider down"))

    with pytest.raises(AgentError):
        await run(make_agent(model), "Hej")


async def test_end_to_end_with_use_case_reports_only_cited_sources() -> None:
    agent = make_agent(ScriptedChatModel(replies=contact_turn()))

    events = [e async for e in AskQuestion(agent).execute(SESSION, Question("Kontakt?"))]

    assert events[-2:] == [
        SourcesEvent(sources=(SourceRef("Kontakta oss", CONTACT.url),)),
        DoneEvent(),
    ]
