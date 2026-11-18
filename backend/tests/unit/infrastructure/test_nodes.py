"""Nodes that do not need a model: tool execution, source collection and fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from compileit_chat.domain.documents import ScoredChunk
from compileit_chat.infrastructure.orchestration.nodes import AgentNodes
from compileit_chat.infrastructure.orchestration.prompts import (
    FALLBACK_ANSWER,
    TOOL_CALL_CANCELLED,
)
from compileit_chat.infrastructure.orchestration.tools import build_tools
from tests.fakes import InMemoryDocumentStore, ParagraphChunker, StaticRetriever, make_document

if TYPE_CHECKING:
    from compileit_chat.infrastructure.orchestration.state import AgentState

PAGE = make_document("https://compileit.com/kontakt", "Mejla oss.", "Kontakta oss")
OTHER = {"title": "Om oss", "url": "https://compileit.com/om-oss"}
CONTACT = {"title": "Kontakta oss", "url": PAGE.url}


def make_nodes() -> AgentNodes:
    hits = [ScoredChunk(c, 1.0) for c in ParagraphChunker().split(PAGE)]
    tools = build_tools(StaticRetriever(hits), InMemoryDocumentStore([PAGE]))
    model = RunnableLambda(lambda _: AIMessage(""))
    return AgentNodes(
        model=model,
        grounding_model=model,
        tools=tools,
        system_prompt="SYSTEM",
        max_history_messages=20,
    )


def calls(*specs: tuple[str, dict[str, Any]]) -> AIMessage:
    return AIMessage(
        "", tool_calls=[{"name": n, "args": a, "id": f"c{i}"} for i, (n, a) in enumerate(specs)]
    )


def state(
    *messages: object, sources: list[dict[str, str]] | None = None, it: int = 0
) -> AgentState:
    return {"messages": list(messages), "sources": sources or [], "tool_iterations": it}  # type: ignore[typeddict-item]


async def test_run_tools_answers_every_call_and_counts_the_round() -> None:
    request = calls(("search_website", {"query": "kontakt"}), ("list_pages", {}))

    update = await make_nodes().run_tools(state(HumanMessage("q"), request, it=1))

    assert [m.tool_call_id for m in update["messages"]] == ["c0", "c1"]
    assert update["messages"][0].artifact == [CONTACT]
    assert update["tool_iterations"] == 2


async def test_run_tools_reports_bad_arguments_and_unknown_tools_to_the_model() -> None:
    request = calls(("search_website", {"k": 99}), ("delete_everything", {}))

    update = await make_nodes().run_tools(state(HumanMessage("q"), request))

    bad_args, unknown = update["messages"]
    assert (bad_args.status, unknown.status) == ("error", "error")
    assert "Ogiltiga argument" in bad_args.content
    assert "Okänt verktyg" in unknown.content


async def test_collect_sources_adds_latest_round_without_duplicates() -> None:
    older_round = ToolMessage("x", tool_call_id="old", artifact=[OTHER])
    latest = [
        ToolMessage("x", tool_call_id="c0", artifact=[CONTACT, OTHER]),
        ToolMessage("x", tool_call_id="c1", artifact=[CONTACT]),
    ]
    current = state(older_round, AIMessage("", tool_calls=[]), *latest, sources=[OTHER])

    update = await make_nodes().collect_sources(current)

    assert update == {"sources": [OTHER, CONTACT]}


async def test_fallback_closes_open_tool_calls_then_answers() -> None:
    request = calls(("search_website", {"query": "x"}), ("get_page", {"url_or_title": "y"}))

    update = await make_nodes().handle_fallback(state(HumanMessage("q"), request, it=4))

    *cancelled, answer = update["messages"]
    assert [(m.tool_call_id, m.content) for m in cancelled] == [
        ("c0", TOOL_CALL_CANCELLED),
        ("c1", TOOL_CALL_CANCELLED),
    ]
    assert answer == AIMessage(FALLBACK_ANSWER)


async def test_first_step_of_a_turn_must_call_a_tool_later_steps_may_answer() -> None:
    used: list[str] = []
    nodes = AgentNodes(
        model=RunnableLambda(lambda _: used.append("free") or AIMessage("svar")),
        grounding_model=RunnableLambda(lambda _: used.append("grounding") or AIMessage("")),
        tools=[],
        system_prompt="SYSTEM",
        max_history_messages=20,
    )

    await nodes.call_model(state(HumanMessage("Följdfråga"), it=0))
    await nodes.call_model(state(HumanMessage("Följdfråga"), it=1))

    assert used == ["grounding", "free"]
