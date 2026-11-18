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

from compileit_chat.domain.errors import DomainError
from compileit_chat.interface.api.log_config import request_id
from compileit_chat.interface.api.rate_limit import SlidingWindowRateLimiter
from compileit_chat.interface.api.routes import router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from contextlib import AbstractAsyncContextManager

    from starlette.responses import Response

    from compileit_chat.container import ChatUseCases

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class Backend(Protocol):
    """What the API needs from the composition root (`Container` in production)."""

    def chat(self) -> AbstractAsyncContextManager[ChatUseCases]: ...

    async def prepare(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ApiConfig:
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    rate_limit_requests: int = 20
    rate_limit_window_seconds: float = 60.0


def create_app(backend: Backend, config: ApiConfig) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await backend.prepare()
        async with backend.chat() as chat:  # one conversation-store connection per process
            app.state.chat = chat
            yield

    app = FastAPI(title="Compileit chat API", version="0.1.0", lifespan=lifespan)
    app.state.rate_limiter = SlidingWindowRateLimiter(
        config.rate_limit_requests, config.rate_limit_window_seconds
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_origins),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.middleware("http")(_request_context)
    app.add_exception_handler(DomainError, _domain_error)
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
