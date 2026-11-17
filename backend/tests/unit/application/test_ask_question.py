from __future__ import annotations

from typing import TYPE_CHECKING

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.use_cases import AskQuestion
from compileit_chat.application.use_cases.ask_question import AGENT_ERROR_MESSAGE
from compileit_chat.domain.conversation import Question, SessionId
from compileit_chat.domain.documents import SourceRef
from tests.fakes import ScriptedAgent

if TYPE_CHECKING:
    from compileit_chat.application.dto import AgentEvent, ChatEvent

SESSION = SessionId("session-0001")
QUESTION = Question("Hur kontaktar man er?")
CONTACT = SourceRef("Kontakt", "https://www.compileit.com/kontakt")
ABOUT = SourceRef("Om oss", "https://www.compileit.com/om-oss")


async def ask(agent: ScriptedAgent) -> list[ChatEvent]:
    return [event async for event in AskQuestion(agent).execute(SESSION, QUESTION)]


async def test_streams_tokens_and_tool_calls_then_cited_sources_and_done() -> None:
    script: list[AgentEvent] = [
        ToolCallEvent(tool="search_website", query="kontakt"),
        RetrievalEvent(sources=(CONTACT, ABOUT)),
        TokenEvent("Mejla oss, se "),
        TokenEvent(f"[Kontakt]({CONTACT.url})."),
    ]

    events = await ask(ScriptedAgent(script))

    assert events == [
        ToolCallEvent(tool="search_website", query="kontakt"),
        TokenEvent("Mejla oss, se "),
        TokenEvent(f"[Kontakt]({CONTACT.url})."),
        SourcesEvent(sources=(CONTACT,)),
        DoneEvent(),
    ]


async def test_passes_session_and_question_to_agent() -> None:
    agent = ScriptedAgent([])

    await ask(agent)

    assert agent.calls == [(SESSION, QUESTION)]


async def test_not_found_answer_has_no_sources() -> None:
    script: list[AgentEvent] = [
        RetrievalEvent(sources=(ABOUT,)),
        TokenEvent("Det hittar jag inte på compileit.com."),
    ]

    events = await ask(ScriptedAgent(script))

    assert events[-2:] == [SourcesEvent(sources=()), DoneEvent()]


async def test_agent_failure_ends_stream_with_single_swedish_error() -> None:
    events = await ask(ScriptedAgent([TokenEvent("Vi ")], fail=True))

    assert events == [TokenEvent("Vi "), ErrorEvent(message=AGENT_ERROR_MESSAGE)]
