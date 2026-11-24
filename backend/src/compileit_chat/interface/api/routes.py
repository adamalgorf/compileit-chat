"""HTTP endpoints. Thin: authenticate, validate, call a use case, serialise."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse

from compileit_chat.application.dto import ErrorEvent
from compileit_chat.application.use_cases.ask_question import AGENT_ERROR_MESSAGE
from compileit_chat.container import AppUseCases
from compileit_chat.domain.accounts import User
from compileit_chat.domain.conversation import Question, SessionId
from compileit_chat.interface.api.schemas import (
    ChatRequest,
    ConversationResponse,
    ConversationSummary,
    ErrorResponse,
    HealthResponse,
    LoginRequest,
    MessageResponse,
    SourceResponse,
    UserResponse,
)
from compileit_chat.interface.api.sse import encode

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import ChatEvent
    from compileit_chat.interface.api.app import ApiConfig
    from compileit_chat.interface.api.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)

RATE_LIMITED_MESSAGE = "För många frågor på kort tid. Vänta en stund och försök igen."
LOGIN_RATE_LIMITED_MESSAGE = "För många inloggningsförsök. Vänta en stund och försök igen."
NOT_LOGGED_IN_MESSAGE = "Du behöver logga in."

router = APIRouter(prefix="/api")


# --- dependencies ------------------------------------------------------------------------


def use_cases(request: Request) -> AppUseCases:
    """Dependency: the app's use cases."""
    app_use_cases: AppUseCases = request.app.state.use_cases
    return app_use_cases


UseCases = Annotated[AppUseCases, Depends(use_cases)]


async def current_user(request: Request, cases: UseCases) -> User:
    """Dependency for protected routes: the user behind the cookie, else 401."""
    config: ApiConfig = request.app.state.config
    user = await cases.authenticate.execute(request.cookies.get(config.cookie_name))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=NOT_LOGGED_IN_MESSAGE)
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def _limit(limiter: SlidingWindowRateLimiter, key: str, message: str) -> None:
    if (retry_after := limiter.retry_after(key)) is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=message,
            headers={"Retry-After": str(max(1, round(retry_after)))},
        )


def limit_chat(request: Request, user: CurrentUser) -> None:
    """Per-user limit on chat requests, since each one costs OpenAI tokens."""
    _limit(request.app.state.rate_limiter, user.id, RATE_LIMITED_MESSAGE)


def limit_login(request: Request) -> None:
    """Per-IP limit on login attempts, against password guessing."""
    client = request.client.host if request.client else "unknown"
    _limit(request.app.state.login_limiter, client, LOGIN_RATE_LIMITED_MESSAGE)


# --- auth --------------------------------------------------------------------------------


@router.post(
    "/auth/login",
    dependencies=[Depends(limit_login)],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def login(
    body: LoginRequest, request: Request, response: Response, cases: UseCases
) -> UserResponse:
    """Check credentials and set an HttpOnly session cookie. Every attempt is logged."""
    config: ApiConfig = request.app.state.config
    client = request.client.host if request.client else None
    result = await cases.login.execute(body.username, body.password, client)
    response.set_cookie(
        config.cookie_name,
        result.token,
        expires=result.expires_at,
        httponly=True,  # not readable by JavaScript, so XSS cannot steal it
        secure=config.cookie_secure,
        samesite="lax",
        path="/api",
    )
    return UserResponse(username=result.user.username.value)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, cases: UseCases) -> Response:
    """End the session server-side and clear the cookie."""
    config: ApiConfig = request.app.state.config
    if token := request.cookies.get(config.cookie_name):
        await cases.logout.execute(token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(config.cookie_name, path="/api")
    return response


@router.get("/auth/me", responses={401: {"model": ErrorResponse}})
async def me(user: CurrentUser) -> UserResponse:
    """The logged-in user; the frontend uses it to choose login screen or chat."""
    return UserResponse(username=user.username.value)


# --- chat --------------------------------------------------------------------------------


@router.post(
    "/chat",
    dependencies=[Depends(limit_chat)],
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "SSE stream, see sse.py"},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def chat(body: ChatRequest, user: CurrentUser, cases: UseCases) -> StreamingResponse:
    """Answer a question in one of the user's conversations, streamed as Server-Sent Events.
    A new conversation id starts a new saved conversation."""
    # Validated, authorised and saved before streaming starts, so problems are plain HTTP
    # errors rather than a broken stream.
    conversation_id, question = SessionId(body.conversation_id), Question(body.message)
    await cases.chat.start(user, conversation_id, question)
    logger.info(
        "Chat request",
        extra={"conversation_id": str(conversation_id), "chars": len(question.text)},
    )
    return StreamingResponse(
        _sse(cases.chat.stream(user, conversation_id, question)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- history -----------------------------------------------------------------------------


@router.get("/conversations", responses={401: {"model": ErrorResponse}})
async def list_conversations(user: CurrentUser, cases: UseCases) -> list[ConversationSummary]:
    """The user's saved conversations, most recently active first."""
    conversations = await cases.list_conversations.execute(user)
    return [
        ConversationSummary(id=str(c.id), title=c.title, updated_at=c.updated_at)
        for c in conversations
    ]


@router.get(
    "/conversations/{conversation_id}",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def get_conversation(
    conversation_id: str, user: CurrentUser, cases: UseCases
) -> ConversationResponse:
    """A saved conversation with its messages, for reopening it."""
    conversation, messages = await cases.get_conversation.execute(user, SessionId(conversation_id))
    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        messages=[
            MessageResponse(
                role=m.role.value,
                content=m.content,
                sources=[SourceResponse(title=s.title, url=s.url) for s in m.sources],
                status=m.status.value if m.status else None,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
async def delete_conversation(conversation_id: str, user: CurrentUser, cases: UseCases) -> Response:
    """Delete the saved conversation and the agent's memory of it."""
    await cases.delete_conversation.execute(user, SessionId(conversation_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/health")
async def health() -> HealthResponse:
    """Liveness check, used by the Docker health check."""
    return HealthResponse(status="ok")


async def _sse(events: AsyncIterator[ChatEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield encode(event)
    except Exception:
        # Headers are already sent, so an HTTP error is impossible; end the stream in-band.
        logger.exception("Unexpected error while streaming")
        yield encode(ErrorEvent(message=AGENT_ERROR_MESSAGE))
