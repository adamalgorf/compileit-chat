"""Request and response bodies. Domain value objects do the real validation."""

from __future__ import annotations

from pydantic import BaseModel, Field

from compileit_chat.domain.conversation import MAX_QUESTION_LENGTH


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=128, examples=["3f2b8c1e-4a5d-4e6f"])
    message: str = Field(
        min_length=1, max_length=MAX_QUESTION_LENGTH, examples=["Vilka branscher jobbar ni med?"]
    )


class HealthResponse(BaseModel):
    status: str


class ErrorResponse(BaseModel):
    detail: str
