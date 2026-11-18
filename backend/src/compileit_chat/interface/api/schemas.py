"""Request and response bodies. Domain value objects do the real validation."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 - pydantic resolves annotations at runtime

from pydantic import BaseModel, Field

from compileit_chat.domain.accounts import MAX_PASSWORD_LENGTH
from compileit_chat.domain.conversation import MAX_QUESTION_LENGTH


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=8, max_length=128, examples=["3f2b8c1e4a5d4e6f"])
    message: str = Field(
        min_length=1, max_length=MAX_QUESTION_LENGTH, examples=["Vilka branscher jobbar ni med?"]
    )


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    username: str


class SourceResponse(BaseModel):
    title: str
    url: str


class ConversationSummary(BaseModel):
    id: str
    title: str
    updated_at: datetime


class MessageResponse(BaseModel):
    role: str
    content: str
    sources: list[SourceResponse]
    status: str | None
    created_at: datetime


class ConversationResponse(BaseModel):
    id: str
    title: str
    messages: list[MessageResponse]


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
