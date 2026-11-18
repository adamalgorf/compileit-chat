"""SQL adapters against a real SQLite file, with the schema created by the Alembic migration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from compileit_chat.application.errors import UserExistsError
from compileit_chat.domain.accounts import User, Username
from compileit_chat.domain.conversation import SessionId
from compileit_chat.domain.documents import SourceRef
from compileit_chat.domain.history import (
    ApiCallRecord,
    CallStatus,
    Conversation,
    Role,
    StoredMessage,
)
from compileit_chat.infrastructure.persistence.database import Database
from compileit_chat.infrastructure.persistence.repositories import (
    SqlApiCallLog,
    SqlAuthSessionStore,
    SqlConversationRepository,
    SqlLoginEventLog,
    SqlUserRepository,
)
from compileit_chat.infrastructure.persistence.secret_store import (
    EncryptedSecretStore,
    SecretDecryptionError,
    generate_master_key,
)
from compileit_chat.infrastructure.security import Argon2PasswordHasher

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

T0 = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
ANNA = User("u-anna", Username("anna"), "hash", T0)
SOURCE = SourceRef("Kontakta oss", "https://compileit.com/kontakt")


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[Database]:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'app.sqlite3').as_posix()}")
    await database.upgrade()  # the real migration, not create_all
    yield database
    await database.dispose()


async def test_migration_is_idempotent(db: Database) -> None:
    await db.upgrade()  # second run is a no-op


async def test_users_are_unique_by_username(db: Database) -> None:
    users = SqlUserRepository(db)
    await users.add(ANNA)

    assert await users.get(ANNA.id) == ANNA
    assert await users.get_by_username(Username("ANNA")) == ANNA
    with pytest.raises(UserExistsError):
        await users.add(User("u-other", Username("anna"), "hash", T0))


async def test_auth_sessions_expire(db: Database) -> None:
    await SqlUserRepository(db).add(ANNA)
    sessions = SqlAuthSessionStore(db)
    await sessions.create("token-hash", ANNA.id, T0 + timedelta(hours=1))

    assert await sessions.user_id_for("token-hash", T0) == ANNA.id
    assert await sessions.user_id_for("token-hash", T0 + timedelta(hours=2)) is None
    await sessions.delete("token-hash")
    assert await sessions.user_id_for("token-hash", T0) is None


async def test_conversation_history_round_trips_in_order(db: Database) -> None:
    await SqlUserRepository(db).add(ANNA)
    repo = SqlConversationRepository(db)
    first, second = SessionId("conversation-1"), SessionId("conversation-2")
    for conversation_id, title in ((first, "Första"), (second, "Andra")):
        await repo.create(Conversation(conversation_id, ANNA.id, title, T0, T0))
    await repo.add_message(first, StoredMessage(Role.USER, "Fråga?", T0 + timedelta(minutes=5)))
    answer = StoredMessage(
        Role.ASSISTANT, "Svar.", T0 + timedelta(minutes=6), (SOURCE,), CallStatus.DONE
    )
    await repo.add_message(first, answer)

    assert [c.title for c in await repo.list_for_user(ANNA.id)] == ["Första", "Andra"]
    messages = await repo.messages(first)
    assert [m.role for m in messages] == [Role.USER, Role.ASSISTANT]
    assert messages[1] == answer
    assert messages[1].created_at.tzinfo is not None  # UTC survives SQLite

    await repo.delete(first)
    assert await repo.get(first) is None
    assert await repo.messages(first) == []


async def test_api_calls_and_login_events_are_recorded(db: Database) -> None:
    await SqlApiCallLog(db).record(
        ApiCallRecord(
            ANNA.id,
            SessionId("conversation-1"),
            "Fråga?",
            "Svar.",
            (SOURCE,),
            ("search_website: kontakt",),
            CallStatus.DONE,
            820,
            2100,
            T0,
        )
    )
    await SqlLoginEventLog(db).record("anna", False, "10.0.0.1", T0)

    async with db.session() as session:
        calls = (await session.execute(text("select status, total_ms, tools from api_calls"))).all()
        events = (await session.execute(text("select username, succeeded from login_events"))).all()
    assert calls == [("done", 2100, '["search_website: kontakt"]')]
    assert events == [("anna", 0)]


async def test_secrets_are_encrypted_at_rest(db: Database) -> None:
    key = SecretStr(generate_master_key())
    store = EncryptedSecretStore(db, key)
    await store.put("openai_api_key", "sk-test-123")
    await store.put("openai_api_key", "sk-test-456")  # overwrite

    async with db.session() as session:
        raw = (await session.execute(text("select ciphertext from secrets"))).scalar_one()
    assert b"sk-test" not in raw
    assert await store.get("openai_api_key") == "sk-test-456"
    assert await store.get("missing") is None
    with pytest.raises(SecretDecryptionError):
        await EncryptedSecretStore(db, SecretStr(generate_master_key())).get("openai_api_key")


def test_argon2_hashes_are_salted_and_verify() -> None:
    hasher = Argon2PasswordHasher()
    first, second = hasher.hash("ett-langt-losenord"), hasher.hash("ett-langt-losenord")

    assert first != second  # salted
    assert first.startswith("$argon2id$")
    assert hasher.verify(first, "ett-langt-losenord")
    assert not hasher.verify(first, "fel")
    assert not hasher.verify("not-a-hash", "fel")
