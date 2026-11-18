"""Chatting with saved history, and browsing or deleting a user's conversations."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.errors import ConversationNotFoundError
from compileit_chat.domain.history import (
    ApiCallRecord,
    CallStatus,
    Conversation,
    Role,
    StoredMessage,
    conversation_title,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import ChatEvent
    from compileit_chat.application.ports import (
        ApiCallLogPort,
        ClockPort,
        ConversationRepositoryPort,
        ConversationStorePort,
    )
    from compileit_chat.application.use_cases.ask_question import AskQuestion
    from compileit_chat.domain.accounts import User
    from compileit_chat.domain.conversation import Question, SessionId
    from compileit_chat.domain.documents import SourceRef


class ChatWithHistory:
    """`AskQuestion` for a logged-in user, saving both sides of the turn and an audit record.

    The answer is saved even when the client disconnects mid-stream (status `stopped`), so
    the history shows what the user actually saw.
    """

    def __init__(
        self,
        ask: AskQuestion,
        conversations: ConversationRepositoryPort,
        api_log: ApiCallLogPort,
        clock: ClockPort,
    ) -> None:
        self._ask = ask
        self._conversations = conversations
        self._api_log = api_log
        self._clock = clock

    async def start(self, user: User, conversation_id: SessionId, question: Question) -> None:
        """Validate ownership and save the question. Call before streaming, so a foreign or
        invalid conversation is rejected with a normal error instead of a broken stream."""
        now = self._clock.now()
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            await self._conversations.create(
                Conversation(conversation_id, user.id, conversation_title(question), now, now)
            )
        elif conversation.user_id != user.id:
            raise ConversationNotFoundError(str(conversation_id))
        await self._conversations.add_message(
            conversation_id, StoredMessage(Role.USER, question.text, now)
        )

    async def stream(
        self, user: User, conversation_id: SessionId, question: Question
    ) -> AsyncIterator[ChatEvent]:
        started = time.perf_counter()
        first_token_ms: int | None = None
        answer: list[str] = []
        tools: list[str] = []
        sources: tuple[SourceRef, ...] = ()
        status = CallStatus.STOPPED  # unless the stream reaches done/error
        try:
            async for event in self._ask.execute(conversation_id, question):
                match event:
                    case TokenEvent(text=text):
                        if first_token_ms is None:
                            first_token_ms = _elapsed_ms(started)
                        answer.append(text)
                    case ToolCallEvent(tool=tool, query=query):
                        tools.append(f"{tool}: {query}" if query else tool)
                    case SourcesEvent(sources=cited):
                        sources = cited
                    case DoneEvent():
                        status = CallStatus.DONE
                    case ErrorEvent(message=message):
                        status = CallStatus.ERROR
                        answer = [message]
                yield event
        finally:
            # Shielded: a disconnect cancels this task, but what was shown is still saved.
            await asyncio.shield(
                self._save(
                    user,
                    conversation_id,
                    question,
                    "".join(answer),
                    sources,
                    tuple(tools),
                    status,
                    first_token_ms,
                    _elapsed_ms(started),
                )
            )

    async def _save(
        self,
        user: User,
        conversation_id: SessionId,
        question: Question,
        answer: str,
        sources: tuple[SourceRef, ...],
        tools: tuple[str, ...],
        status: CallStatus,
        first_token_ms: int | None,
        total_ms: int,
    ) -> None:
        now = self._clock.now()
        await self._conversations.add_message(
            conversation_id, StoredMessage(Role.ASSISTANT, answer, now, sources, status)
        )
        await self._api_log.record(
            ApiCallRecord(
                user_id=user.id,
                conversation_id=conversation_id,
                question=question.text,
                answer=answer,
                sources=sources,
                tools=tools,
                status=status,
                first_token_ms=first_token_ms,
                total_ms=total_ms,
                created_at=now,
            )
        )


class ListConversations:
    def __init__(self, conversations: ConversationRepositoryPort) -> None:
        self._conversations = conversations

    async def execute(self, user: User) -> list[Conversation]:
        return await self._conversations.list_for_user(user.id)


class GetConversation:
    def __init__(self, conversations: ConversationRepositoryPort) -> None:
        self._conversations = conversations

    async def execute(
        self, user: User, conversation_id: SessionId
    ) -> tuple[Conversation, list[StoredMessage]]:
        conversation = await _owned(self._conversations, user, conversation_id)
        return conversation, await self._conversations.messages(conversation_id)


class DeleteConversation:
    """Delete the saved history and the agent's memory of the conversation."""

    def __init__(
        self, conversations: ConversationRepositoryPort, agent_memory: ConversationStorePort
    ) -> None:
        self._conversations = conversations
        self._agent_memory = agent_memory

    async def execute(self, user: User, conversation_id: SessionId) -> None:
        await _owned(self._conversations, user, conversation_id)
        await self._conversations.delete(conversation_id)
        await self._agent_memory.reset(conversation_id)


async def _owned(
    conversations: ConversationRepositoryPort, user: User, conversation_id: SessionId
) -> Conversation:
    """The conversation if it belongs to the user. Someone else's looks exactly like a
    missing one, so ids cannot be probed."""
    conversation = await conversations.get(conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise ConversationNotFoundError(str(conversation_id))
    return conversation


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
