"""Value objects for a chat session."""

from __future__ import annotations

import re
from dataclasses import dataclass

from compileit_chat.domain.errors import InvalidQuestionError, InvalidSessionIdError

MAX_QUESTION_LENGTH = 2000
_SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}")


@dataclass(frozen=True, slots=True)
class SessionId:
    """Client-generated conversation id (typically a UUID). Restricted to a URL-safe charset."""

    value: str

    def __post_init__(self) -> None:
        if not _SESSION_ID_PATTERN.fullmatch(self.value):
            raise InvalidSessionIdError("Session id must be 8-128 chars of [A-Za-z0-9_-].")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Question:
    """A user question, stripped of surrounding whitespace and bounded in length."""

    text: str

    def __post_init__(self) -> None:
        stripped = self.text.strip()
        if not stripped:
            raise InvalidQuestionError("Question must not be empty.")
        if len(stripped) > MAX_QUESTION_LENGTH:
            raise InvalidQuestionError(f"Question must be at most {MAX_QUESTION_LENGTH} chars.")
        object.__setattr__(self, "text", stripped)

    def __str__(self) -> str:
        return self.text
