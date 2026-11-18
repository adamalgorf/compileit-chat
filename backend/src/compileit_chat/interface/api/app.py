"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from compileit_chat.application.errors import AuthenticationError, ConversationNotFoundError
from compileit_chat.domain.errors import DomainError
from compileit_chat.interface.api.log_config import request_id
from compileit_chat.interface.api.rate_limit import SlidingWindowRateLimiter
from compileit_chat.interface.api.routes import router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from contextlib import AbstractAsyncContextManager

    from starlette.responses import Response

    from compileit_chat.container import AppUseCases

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class Backend(Protocol):
    """What the API needs from the composition root (`Container` in production)."""

    def use_cases(self) -> AbstractAsyncContextManager[AppUseCases]: ...

    async def prepare(self) -> None: ...

    async def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ApiConfig:
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    rate_limit_requests: int = 20  # chat requests per user per window
    rate_limit_window_seconds: float = 60.0
    login_attempts: int = 10  # per client IP per window (slows down password guessing)
    login_window_seconds: float = 300.0
    cookie_name: str = "compileit_session"
    cookie_secure: bool = False  # true behind HTTPS


def create_app(backend: Backend, config: ApiConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await backend.prepare()  # migrate the database, load secrets, build the index if needed
        try:
            async with backend.use_cases() as use_cases:
                app.state.use_cases = use_cases
                yield
        finally:
            await backend.stop()

    app = FastAPI(title="Compileit chat API", version="0.1.0", lifespan=lifespan)
    app.state.config = config
    app.state.rate_limiter = SlidingWindowRateLimiter(
        config.rate_limit_requests, config.rate_limit_window_seconds
    )
    app.state.login_limiter = SlidingWindowRateLimiter(
        config.login_attempts, config.login_window_seconds
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_credentials=True,  # the session cookie; requires explicit origins (no "*")
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.middleware("http")(_request_context)
    app.add_exception_handler(DomainError, _domain_error)
    app.add_exception_handler(AuthenticationError, _authentication_error)
    app.add_exception_handler(ConversationNotFoundError, _not_found)
    app.include_router(router)
    return app


async def _request_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Tag the request with an id (client-supplied or new) and log one line per request."""
    token = request_id.set(request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id.get() or ""
        logger.info(
            "Request handled",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000),
            },
        )
        return response
    finally:
        request_id.reset(token)


async def _domain_error(request: Request, error: Exception) -> JSONResponse:
    # Invalid session id or question: the client's fault, reported like schema errors.
    return JSONResponse({"detail": str(error)}, status_code=status.HTTP_422_UNPROCESSABLE_CONTENT)


async def _authentication_error(request: Request, error: Exception) -> JSONResponse:
    # Same message for unknown user and wrong password: usernames cannot be probed.
    return JSONResponse(
        {"detail": "Fel användarnamn eller lösenord."}, status_code=status.HTTP_401_UNAUTHORIZED
    )


async def _not_found(request: Request, error: Exception) -> JSONResponse:
    return JSONResponse(
        {"detail": "Konversationen finns inte."}, status_code=status.HTTP_404_NOT_FOUND
    )
