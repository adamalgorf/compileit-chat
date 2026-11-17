"""Start over: forget everything said in a session."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compileit_chat.application.ports import ConversationStorePort
    from compileit_chat.domain.conversation import SessionId


class ResetConversation:
    def __init__(self, store: ConversationStorePort) -> None:
        self._store = store

    async def execute(self, session_id: SessionId) -> None:
        await self._store.reset(session_id)
