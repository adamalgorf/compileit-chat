import asyncio
from datetime import UTC, datetime

import pytest

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    RetrievalEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.errors import ConversationNotFoundError
from compileit_chat.application.use_cases import (
    AskQuestion,
    ChatWithHistory,
    DeleteConversation,
    GetConversation,
    ListConversations,
)
from compileit_chat.domain.accounts import User, Username
from compileit_chat.domain.conversation import Question, SessionId
from compileit_chat.domain.documents import SourceRef
from compileit_chat.domain.history import CallStatus, Role
from tests.fakes import (
    ApiCallRecorder,
    FixedClock,
    InMemoryConversations,
    InMemoryConversationStore,
    ScriptedAgent,
)

ANNA = User("u-anna", Username("anna"), "h", datetime(2026, 1, 1, tzinfo=UTC))
BERTIL = User("u-bertil", Username("bertil"), "h", datetime(2026, 1, 1, tzinfo=UTC))
CONVERSATION = SessionId("conversation-1")
QUESTION = Question("Hur kontaktar man er?")
CONTACT = SourceRef("Kontakta oss", "https://compileit.com/kontakt")
ANSWER_SCRIPT = [
    ToolCallEvent("search_website", "kontakt"),
    RetrievalEvent((CONTACT,)),
    TokenEvent("Mejla oss, se "),
    TokenEvent(f"[Kontakta oss]({CONTACT.url})."),
]


class History:
    def __init__(self, script: list[object] | None = None, *, fail: bool = False) -> None:
        self.conversations = InMemoryConversations()
        self.api_log = ApiCallRecorder()
        agent = ScriptedAgent(script if script is not None else ANSWER_SCRIPT, fail=fail)  # type: ignore[arg-type]
        self.chat = ChatWithHistory(
            AskQuestion(agent), self.conversations, self.api_log, FixedClock()
        )

    async def ask(self, user: User = ANNA, conversation: SessionId = CONVERSATION) -> list[object]:
        await self.chat.start(user, conversation, QUESTION)
        return [e async for e in self.chat.stream(user, conversation, QUESTION)]


async def test_a_turn_saves_question_answer_and_audit_record() -> None:
    history = History()

    events = await history.ask()

    assert events[-1] == DoneEvent()
    [saved] = await history.conversations.list_for_user(ANNA.id)
    assert saved.title == QUESTION.text
    question, answer = await history.conversations.messages(CONVERSATION)
    assert (question.role, question.content) == (Role.USER, QUESTION.text)
    assert (answer.role, answer.status, answer.sources) == (
        Role.ASSISTANT,
        CallStatus.DONE,
        (CONTACT,),
    )
    assert answer.content == f"Mejla oss, se [Kontakta oss]({CONTACT.url})."
    [call] = history.api_log.calls
    assert (call.user_id, call.status, call.tools) == (
        ANNA.id,
        CallStatus.DONE,
        ("search_website: kontakt",),
    )
    assert call.first_token_ms is not None


async def test_a_failed_turn_is_saved_with_the_error_shown() -> None:
    history = History([TokenEvent("Halv")], fail=True)

    events = await history.ask()

    assert isinstance(events[-1], ErrorEvent)
    _, answer = await history.conversations.messages(CONVERSATION)
    assert (answer.status, answer.content) == (CallStatus.ERROR, events[-1].message)
    assert history.api_log.calls[0].status == CallStatus.ERROR


async def test_a_disconnect_mid_answer_still_saves_what_was_shown() -> None:
    history = History()
    await history.chat.start(ANNA, CONVERSATION, QUESTION)
    stream = history.chat.stream(ANNA, CONVERSATION, QUESTION)

    await anext(stream)  # tool call
    await anext(stream)  # first token
    await stream.aclose()  # the client went away
    await asyncio.sleep(0)

    _, answer = await history.conversations.messages(CONVERSATION)
    assert (answer.status, answer.content) == (CallStatus.STOPPED, "Mejla oss, se ")
    assert history.api_log.calls[0].status == CallStatus.STOPPED


async def test_someone_elses_conversation_cannot_be_continued_read_or_deleted() -> None:
    history = History()
    await history.ask(ANNA)

    with pytest.raises(ConversationNotFoundError):
        await history.chat.start(BERTIL, CONVERSATION, QUESTION)
    with pytest.raises(ConversationNotFoundError):
        await GetConversation(history.conversations).execute(BERTIL, CONVERSATION)
    with pytest.raises(ConversationNotFoundError):
        await DeleteConversation(history.conversations, InMemoryConversationStore()).execute(
            BERTIL, CONVERSATION
        )
    assert await ListConversations(history.conversations).execute(BERTIL) == []


async def test_follow_up_turns_append_to_the_same_conversation() -> None:
    history = History()

    await history.ask()
    await history.ask()

    assert len(await history.conversations.list_for_user(ANNA.id)) == 1
    assert len(await history.conversations.messages(CONVERSATION)) == 4


async def test_delete_removes_history_and_agent_memory() -> None:
    history = History()
    await history.ask()
    memory = InMemoryConversationStore({CONVERSATION})

    await DeleteConversation(history.conversations, memory).execute(ANNA, CONVERSATION)

    assert await history.conversations.get(CONVERSATION) is None
    assert memory.sessions == set()
    assert len(history.api_log.calls) == 1  # the audit record outlives the conversation
