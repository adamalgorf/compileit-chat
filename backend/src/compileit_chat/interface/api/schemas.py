"""Request and response bodies. Domain value objects do the real validation."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - pydantic resolves annotations at runtime

from pydantic import BaseModel, Field

from compileit_chat.domain.accounts import MAX_PASSWORD_LENGTH
from compileit_chat.domain.conversation import MAX_QUESTION_LENGTH


class ChatRequest(BaseModel):
    """Body of `POST /api/chat`. The client creates the conversation id."""

    conversation_id: str = Field(min_length=8, max_length=128, examples=["3f2b8c1e4a5d4e6f"])
    message: str = Field(
        min_length=1, max_length=MAX_QUESTION_LENGTH, examples=["Vilka branscher jobbar ni med?"]
    )


class LoginRequest(BaseModel):
    """Body of `POST /api/auth/login`."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    """The logged-in user."""

    username: str


class SourceResponse(BaseModel):
    """A page the answer cites."""

    title: str
    url: str


class ConversationSummary(BaseModel):
    """One row of the history list."""

    id: str
    title: str
    updated_at: datetime


class MessageResponse(BaseModel):
    """One saved message; `status` is set on assistant messages only."""

    role: str
    content: str
    sources: list[SourceResponse]
    status: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    """A conversation with all its messages."""

    id: str
    title: str
    messages: list[MessageResponse]


class HealthResponse(BaseModel):
    """Body of `GET /api/health`."""

    status: str


class ErrorResponse(BaseModel):
    """Error body. `detail` is a Swedish message that is safe to show."""

    detail: str
