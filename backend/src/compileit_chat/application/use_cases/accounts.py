"""Creating users, logging in and out, and resolving the user behind a session token."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from compileit_chat.application.errors import AuthenticationError
from compileit_chat.domain.accounts import User, Username, validate_new_password
from compileit_chat.domain.errors import InvalidUsernameError

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from compileit_chat.application.ports import (
        AuthSessionStorePort,
        ClockPort,
        LoginEventLogPort,
        PasswordHasherPort,
        UserRepositoryPort,
    )


def hash_token(token: str) -> str:
    """Session tokens are stored hashed, so a leaked database cannot be used to log in."""
    return hashlib.sha256(token.encode()).hexdigest()


class CreateUser:
    """Create an account (done by an admin via the CLI). Enforces the username and password rules
    and stores only the password hash.
    """

    def __init__(
        self, users: UserRepositoryPort, hasher: PasswordHasherPort, clock: ClockPort
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._clock = clock

    async def execute(self, username: str, password: str) -> User:
        name = Username(username)
        validate_new_password(password, name)
        user = User(
            id=uuid.uuid4().hex,
            username=name,
            password_hash=self._hasher.hash(password),
            created_at=self._clock.now(),
        )
        await self._users.add(user)
        return user


@dataclass(frozen=True, slots=True)
class LoginResult:
    """A successful login: the user, and the raw session token for the cookie."""

    user: User
    token: str  # give to the client once (cookie); only its hash is stored
    expires_at: datetime


class Login:
    """Check credentials, record the attempt, and open a session on success."""

    def __init__(
        self,
        users: UserRepositoryPort,
        hasher: PasswordHasherPort,
        sessions: AuthSessionStorePort,
        login_events: LoginEventLogPort,
        clock: ClockPort,
        session_ttl: timedelta,
    ) -> None:
        self._users = users
        self._hasher = hasher
        self._sessions = sessions
        self._login_events = login_events
        self._clock = clock
        self._session_ttl = session_ttl
        # Verified when the username is unknown, so both failure paths take as long and
        # response timing does not reveal which usernames exist.
        self._dummy_hash = hasher.hash(secrets.token_urlsafe(16))

    async def execute(self, username: str, password: str, client: str | None) -> LoginResult:
        """Raises `AuthenticationError` with the same message whether the username or the password
        is wrong, so the response does not reveal which accounts exist.
        """
        now = self._clock.now()
        user = await self._find(username)
        valid = self._hasher.verify(user.password_hash if user else self._dummy_hash, password)
        succeeded = bool(user and user.is_active and valid)
        await self._login_events.record(username.strip()[:64], succeeded, client, now)
        if not succeeded or user is None:
            raise AuthenticationError("Fel användarnamn eller lösenord.")

        token = secrets.token_urlsafe(32)
        expires_at = now + self._session_ttl
        await self._sessions.create(hash_token(token), user.id, expires_at)
        return LoginResult(user=user, token=token, expires_at=expires_at)

    async def _find(self, username: str) -> User | None:
        try:
            return await self._users.get_by_username(Username(username))
        except InvalidUsernameError:
            return None


class Logout:
    """End a session by deleting it server-side, which makes the cookie worthless."""

    def __init__(self, sessions: AuthSessionStorePort) -> None:
        self._sessions = sessions

    async def execute(self, token: str) -> None:
        await self._sessions.delete(hash_token(token))


class Authenticate:
    """The active user behind a session token, or None."""

    def __init__(
        self, sessions: AuthSessionStorePort, users: UserRepositoryPort, clock: ClockPort
    ) -> None:
        self._sessions = sessions
        self._users = users
        self._clock = clock

    async def execute(self, token: str | None) -> User | None:
        """The logged-in user for a session token, or None if the token is missing, unknown or
        expired, or the account is disabled.
        """
        if not token:
            return None
        user_id = await self._sessions.user_id_for(hash_token(token), self._clock.now())
        user = await self._users.get(user_id) if user_id else None
        return user if user and user.is_active else None
