"""SQL implementations of the account, history and audit ports."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from compileit_chat.application.errors import UserExistsError
from compileit_chat.domain.accounts import User, Username
from compileit_chat.domain.conversation import SessionId
from compileit_chat.domain.documents import SourceRef
from compileit_chat.domain.history import CallStatus, Conversation, Role, StoredMessage
from compileit_chat.infrastructure.persistence.models import (
    ApiCallRow,
    AuthSessionRow,
    ConversationRow,
    LoginEventRow,
    MessageRow,
    UserRow,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

    from compileit_chat.domain.history import ApiCallRecord
    from compileit_chat.infrastructure.persistence.database import Database


class SqlUserRepository:
    """`UserRepositoryPort` over SQL."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, user_id: str) -> User | None:
        async with self._db.session() as session:
            row = await session.get(UserRow, user_id)
            return _user(row) if row else None

    async def get_by_username(self, username: Username) -> User | None:
        async with self._db.session() as session:
            row = await session.scalar(select(UserRow).where(UserRow.username == username.value))
            return _user(row) if row else None

    async def add(self, user: User) -> None:
        async with self._db.session() as session:
            session.add(
                UserRow(
                    id=user.id,
                    username=user.username.value,
                    password_hash=user.password_hash,
                    is_active=user.is_active,
                    created_at=user.created_at,
                )
            )
            try:
                await session.commit()
            except IntegrityError as error:
                raise UserExistsError(
                    f"Användarnamnet {user.username.value} finns redan."
                ) from error


class SqlAuthSessionStore:
    """`AuthSessionStorePort` over SQL; rows are keyed by token hash."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def create(self, token_hash: str, user_id: str, expires_at: datetime) -> None:
        async with self._db.session() as session:
            session.add(
                AuthSessionRow(token_hash=token_hash, user_id=user_id, expires_at=expires_at)
            )
            await session.commit()

    async def user_id_for(self, token_hash: str, now: datetime) -> str | None:
        """An expired session counts as missing."""
        async with self._db.session() as session:
            row = await session.get(AuthSessionRow, token_hash)
            return row.user_id if row and row.expires_at > now else None

    async def delete(self, token_hash: str) -> None:
        async with self._db.session() as session:
            await session.execute(
                delete(AuthSessionRow).where(AuthSessionRow.token_hash == token_hash)
            )
            await session.commit()


class SqlLoginEventLog:
    """`LoginEventLogPort` over SQL."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def record(
        self, username: str, succeeded: bool, client: str | None, at: datetime
    ) -> None:
        async with self._db.session() as session:
            session.add(LoginEventRow(username=username, succeeded=succeeded, client=client, at=at))
            await session.commit()


class SqlConversationRepository:
    """`ConversationRepositoryPort` over SQL."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, conversation_id: SessionId) -> Conversation | None:
        async with self._db.session() as session:
            row = await session.get(ConversationRow, str(conversation_id))
            return _conversation(row) if row else None

    async def create(self, conversation: Conversation) -> None:
        async with self._db.session() as session:
            session.add(
                ConversationRow(
                    id=str(conversation.id),
                    user_id=conversation.user_id,
                    title=conversation.title,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                )
            )
            await session.commit()

    async def list_for_user(self, user_id: str) -> list[Conversation]:
        async with self._db.session() as session:
            rows = await session.scalars(
                select(ConversationRow)
                .where(ConversationRow.user_id == user_id)
                .order_by(ConversationRow.updated_at.desc())
            )
            return [_conversation(row) for row in rows]

    async def messages(self, conversation_id: SessionId) -> list[StoredMessage]:
        async with self._db.session() as session:
            rows = await session.scalars(
                select(MessageRow)
                .where(MessageRow.conversation_id == str(conversation_id))
                .order_by(MessageRow.id)
            )
            return [_message(row) for row in rows]

    async def add_message(self, conversation_id: SessionId, message: StoredMessage) -> None:
        async with self._db.session() as session:
            session.add(
                MessageRow(
                    conversation_id=str(conversation_id),
                    role=message.role.value,
                    content=message.content,
                    sources=_sources_json(message.sources),
                    status=message.status.value if message.status else None,
                    created_at=message.created_at,
                )
            )
            conversation = await session.get(ConversationRow, str(conversation_id))
            if conversation is not None:
                conversation.updated_at = message.created_at
            await session.commit()

    async def delete(self, conversation_id: SessionId) -> None:
        async with self._db.session() as session:
            # Explicit, not only ON DELETE CASCADE, so other databases behave the same.
            await session.execute(
                delete(MessageRow).where(MessageRow.conversation_id == str(conversation_id))
            )
            await session.execute(
                delete(ConversationRow).where(ConversationRow.id == str(conversation_id))
            )
            await session.commit()


class SqlApiCallLog:
    """`ApiCallLogPort` over SQL."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def record(self, call: ApiCallRecord) -> None:
        async with self._db.session() as session:
            session.add(
                ApiCallRow(
                    user_id=call.user_id,
                    conversation_id=str(call.conversation_id),
                    question=call.question,
                    answer=call.answer,
                    sources=_sources_json(call.sources),
                    tools=list(call.tools),
                    status=call.status.value,
                    first_token_ms=call.first_token_ms,
                    total_ms=call.total_ms,
                    created_at=call.created_at,
                )
            )
            await session.commit()


def _user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=Username(row.username),
        password_hash=row.password_hash,
        created_at=row.created_at,
        is_active=row.is_active,
    )


def _conversation(row: ConversationRow) -> Conversation:
    return Conversation(
        id=SessionId(row.id),
        user_id=row.user_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _message(row: MessageRow) -> StoredMessage:
    return StoredMessage(
        role=Role(row.role),
        content=row.content,
        created_at=row.created_at,
        sources=tuple(SourceRef(s["title"], s["url"]) for s in row.sources or []),
        status=CallStatus(row.status) if row.status else None,
    )


def _sources_json(sources: Iterable[SourceRef]) -> list[dict[str, str]]:
    return [{"title": s.title, "url": s.url} for s in sources]
