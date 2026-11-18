"""Password hashing and the system clock."""

from __future__ import annotations

from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


class Argon2PasswordHasher:
    """Argon2id with argon2-cffi's defaults (OWASP-recommended memory-hard parameters)."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher()

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)
