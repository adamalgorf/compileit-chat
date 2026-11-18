"""The real orchestration graph, tools and checkpointers, driven by a scripted chat model.

Covers tool call -> answer, the max-iteration fallback, follow-ups in the same thread_id,
reset, persistence across restarts and error translation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
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
from compileit_chat.domain.documents import SourceRef
from compileit_chat.infrastructure.orchestration.prompts import FALLBACK_ANSWER
from tests.agent_factory import CONTACT, CONTACT_ANSWER, contact_turn, make_orchestrator
from tests.scripted_chat_model import ScriptedChatModel, tool_call

if TYPE_CHECKING:
    from pathlib import Path

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.infrastructure.orchestration.orchestrator import LangGraphOrchestrator

SESSION = SessionId("session-0001")
ANSWER = CONTACT_ANSWER


async def run(
    agent: LangGraphOrchestrator, question: str, session: SessionId = SESSION
) -> list[AgentEvent]:
    return [event async for event in agent.stream(session, Question(question))]


async def test_streams_tool_call_retrieval_and_answer_tokens() -> None:
    events = await run(
        make_orchestrator(ScriptedChatModel(replies=contact_turn())), "Hur kontaktar man er?"
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

    await run(make_orchestrator(model), "Hur kontaktar man er?")

    second_call = model.received[1]
    assert second_call[0].content == "SYSTEM"
    assert "<källa" in str(second_call[-1].content)  # the tool result, delimited


async def test_follow_up_sees_earlier_turn_but_other_sessions_do_not() -> None:
    model = ScriptedChatModel(replies=[*contact_turn(), AIMessage("Svar 2"), AIMessage("Svar 3")])
    agent = make_orchestrator(model)

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
    agent = make_orchestrator(model)

    await run(agent, "Fråga 1")
    await agent.reset(SESSION)
    await run(agent, "Fråga 2")

    assert [m.content for m in model.received[1] if isinstance(m, HumanMessage)] == ["Fråga 2"]


async def test_sessions_survive_a_restart_with_sqlite(tmp_path: Path) -> None:
    db = str(tmp_path / "checkpoints.sqlite3")
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        await run(
            make_orchestrator(ScriptedChatModel(replies=[AIMessage("Svar 1")]), saver), "Fråga 1"
        )

    model = ScriptedChatModel(replies=[AIMessage("Svar 2")])
    async with AsyncSqliteSaver.from_conn_string(db) as saver:  # "restarted" process
        await run(make_orchestrator(model, saver), "Fråga 2")

    assert [m.content for m in model.received[0] if isinstance(m, HumanMessage)] == [
        "Fråga 1",
        "Fråga 2",
    ]


async def test_spent_tool_budget_routes_to_fallback_answer() -> None:
    model = ScriptedChatModel(replies=[tool_call("search_website", query="x")], repeat_last=True)

    events = await run(make_orchestrator(model, max_tool_iterations=2), "Loopa")

    tool_starts = [e for e in events if isinstance(e, ToolCallEvent)]
    assert tool_starts == [ToolCallEvent(tool="search_website", query="x")] * 2
    assert events[-1] == TokenEvent(FALLBACK_ANSWER)
    assert len(model.received) == 3  # two tool rounds, then the request that was refused


async def test_conversation_stays_valid_after_a_fallback() -> None:
    loop = [tool_call("search_website", call_id=f"call-{i}", query="x") for i in range(3)]
    model = ScriptedChatModel(replies=[*loop, AIMessage("Svar")])
    agent = make_orchestrator(model, max_tool_iterations=2)

    await run(agent, "Loopa")
    await run(agent, "Nästa fråga")

    next_turn = model.received[-1]
    requested = {c["id"] for m in next_turn if isinstance(m, AIMessage) for c in m.tool_calls}
    answered = {m.tool_call_id for m in next_turn if isinstance(m, ToolMessage)}
    assert requested == answered == {"call-0", "call-1", "call-2"}  # incl. the cancelled one


async def test_provider_errors_become_agent_errors() -> None:
    model = ScriptedChatModel(replies=[], error=ConnectionError("provider down"))

    with pytest.raises(AgentError):
        await run(make_orchestrator(model), "Hej")


async def test_end_to_end_with_use_case_reports_only_cited_sources() -> None:
    agent = make_orchestrator(ScriptedChatModel(replies=contact_turn()))

    events = [e async for e in AskQuestion(agent).execute(SESSION, Question("Kontakt?"))]

    assert events[-2:] == [
        SourcesEvent(sources=(SourceRef("Kontakta oss", CONTACT.url),)),
        DoneEvent(),
    ]
