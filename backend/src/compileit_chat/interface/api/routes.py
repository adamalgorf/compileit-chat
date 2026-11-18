"""HTTP endpoints. Thin: validate, call a use case, serialise."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from compileit_chat.application.dto import ErrorEvent
from compileit_chat.application.use_cases.ask_question import AGENT_ERROR_MESSAGE
from compileit_chat.container import ChatUseCases
from compileit_chat.domain.conversation import Question, SessionId
from compileit_chat.interface.api.schemas import ChatRequest, ErrorResponse, HealthResponse
from compileit_chat.interface.api.sse import encode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import ChatEvent
    from compileit_chat.interface.api.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

RATE_LIMITED_MESSAGE = "För många frågor på kort tid. Vänta en stund och försök igen."

router = APIRouter(prefix="/api")


def chat_use_cases(request: Request) -> ChatUseCases:
    use_cases: ChatUseCases = request.app.state.chat
    return use_cases


def enforce_rate_limit(request: Request) -> None:
    limiter: SlidingWindowRateLimiter = request.app.state.rate_limiter
    client = request.client.host if request.client else "unknown"
    if (retry_after := limiter.retry_after(client)) is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMITED_MESSAGE,
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )


Chat = Annotated[ChatUseCases, Depends(chat_use_cases)]


@router.post(
    "/chat",
    dependencies=[Depends(enforce_rate_limit)],
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "SSE stream, see sse.py"},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def chat(body: ChatRequest, use_cases: Chat) -> StreamingResponse:
    """Answer a question in a session, streamed as Server-Sent Events."""
    # Validated before streaming starts, so bad input is a plain 422, not a broken stream.
    session_id, question = SessionId(body.session_id), Question(body.message)
    logger.info("Chat request", extra={"session_id": str(session_id), "chars": len(question.text)})
    return StreamingResponse(
        _sse(use_cases.ask.execute(session_id, question)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={422: {"model": ErrorResponse}},
)
async def reset_session(session_id: str, use_cases: Chat) -> Response:
    """Forget a conversation ("Ny konversation")."""
    await use_cases.reset.execute(SessionId(session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


async def _sse(events: AsyncIterator[ChatEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield encode(event)
    except Exception:
        # Headers are already sent, so an HTTP error is impossible; end the stream in-band.
        logger.exception("Unexpected error while streaming")
        yield encode(ErrorEvent(message=AGENT_ERROR_MESSAGE))
