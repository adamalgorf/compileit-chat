"""Ports for user accounts, login sessions and secrets."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from datetime import datetime

    from compileit_chat.domain.accounts import User, Username


class UserRepositoryPort(Protocol):
    async def get(self, user_id: str) -> User | None: ...

    async def get_by_username(self, username: Username) -> User | None: ...

    async def add(self, user: User) -> None:
        """Raises `UserExistsError` if the username is taken."""
        ...


class PasswordHasherPort(Protocol):
    """A slow, salted password hash (e.g. Argon2id). Plain passwords never leave the call."""

    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...


class AuthSessionStorePort(Protocol):
    """Server-side login sessions. Only a hash of the session token is stored."""

    async def create(self, token_hash: str, user_id: str, expires_at: datetime) -> None: ...

    async def user_id_for(self, token_hash: str, now: datetime) -> str | None:
        """The session's user, or None if unknown or expired."""
        ...

    async def delete(self, token_hash: str) -> None: ...


class LoginEventLogPort(Protocol):
    async def record(
        self, username: str, succeeded: bool, client: str | None, at: datetime
    ) -> None: ...


class SecretStorePort(Protocol):
    """Named secrets (e.g. the OpenAI API key), encrypted at rest by the adapter."""

    async def get(self, name: str) -> str | None: ...

    async def put(self, name: str, value: str) -> None: ...
