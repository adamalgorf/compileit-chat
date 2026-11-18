"""`SecretStorePort` adapter: secrets in the database, encrypted with Fernet (AES-128-CBC +
HMAC-SHA256). The master key comes from the environment, never from code or the database:
whoever reads the database alone cannot read the secrets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cryptography.fernet import Fernet, InvalidToken

from compileit_chat.infrastructure.persistence.models import SecretRow

if TYPE_CHECKING:
    from pydantic import SecretStr

    from compileit_chat.infrastructure.persistence.database import Database


class SecretDecryptionError(Exception):
    """A stored secret cannot be decrypted: the master key changed or the data is corrupt."""


class EncryptedSecretStore:
    def __init__(self, db: Database, master_key: SecretStr) -> None:
        self._db = db
        self._fernet = Fernet(master_key.get_secret_value())

    async def get(self, name: str) -> str | None:
        async with self._db.session() as session:
            row = await session.get(SecretRow, name)
        if row is None:
            return None
        try:
            return self._fernet.decrypt(row.ciphertext).decode()
        except InvalidToken as error:
            raise SecretDecryptionError(f"Cannot decrypt secret {name!r}.") from error

    async def put(self, name: str, value: str) -> None:
        ciphertext = self._fernet.encrypt(value.encode())
        async with self._db.session() as session:
            row = await session.get(SecretRow, name)
            if row is None:
                session.add(
                    SecretRow(name=name, ciphertext=ciphertext, updated_at=datetime.now(UTC))
                )
            else:
                row.ciphertext, row.updated_at = ciphertext, datetime.now(UTC)
            await session.commit()


def generate_master_key() -> str:
    """A new random master key, to put in SECRETS_MASTER_KEY."""
    return Fernet.generate_key().decode()
