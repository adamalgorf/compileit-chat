"""Ports for saved conversations and the API call log."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from compileit_chat.domain.conversation import SessionId
    from compileit_chat.domain.history import ApiCallRecord, Conversation, StoredMessage


class ConversationRepositoryPort(Protocol):
    async def get(self, conversation_id: SessionId) -> Conversation | None: ...

    async def create(self, conversation: Conversation) -> None: ...

    async def list_for_user(self, user_id: str) -> list[Conversation]:
        """Most recently updated first."""
        ...

    async def messages(self, conversation_id: SessionId) -> list[StoredMessage]:
        """Oldest first."""
        ...

    async def add_message(self, conversation_id: SessionId, message: StoredMessage) -> None:
        """Appends the message and marks the conversation as updated at its time."""
        ...

    async def delete(self, conversation_id: SessionId) -> None: ...


class ApiCallLogPort(Protocol):
    async def record(self, call: ApiCallRecord) -> None: ...


class ClockPort(Protocol):
    def now(self) -> datetime: ...
