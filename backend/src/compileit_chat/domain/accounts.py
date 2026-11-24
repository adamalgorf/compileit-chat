"""User accounts: usernames, password rules and the user entity. Passwords are never stored
here in plain text; only a hash produced by the `PasswordHasherPort` adapter."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from compileit_chat.domain.errors import InvalidUsernameError, WeakPasswordError

if TYPE_CHECKING:
    from datetime import datetime

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256  # bounds hashing cost for hostile input
_USERNAME = re.compile(r"[a-z0-9][a-z0-9._-]{2,63}")


@dataclass(frozen=True, slots=True)
class Username:
    """Case-insensitive login name: 3-64 chars of a-z, 0-9, '.', '_' and '-'."""

    value: str

    def __post_init__(self) -> None:
        normalised = self.value.strip().casefold()
        if not _USERNAME.fullmatch(normalised):
            raise InvalidUsernameError(
                "Användarnamnet ska vara 3–64 tecken: a–z, 0–9, punkt, understreck "
                "eller bindestreck."
            )
        object.__setattr__(self, "value", normalised)

    def __str__(self) -> str:
        return self.value


def validate_new_password(password: str, username: Username) -> None:
    """Rules for a password being set (not for checking one at login)."""
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Lösenordet ska vara {MIN_PASSWORD_LENGTH}–{MAX_PASSWORD_LENGTH} tecken."
        )
    if username.value in password.casefold():
        raise WeakPasswordError("Lösenordet får inte innehålla användarnamnet.")


@dataclass(frozen=True, slots=True)
class User:
    """An account. Only the password's hash is kept, never the password."""

    id: str
    username: Username
    password_hash: str
    created_at: datetime
    is_active: bool = True
