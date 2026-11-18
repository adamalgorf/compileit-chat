import json
import logging

import pytest

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.domain.documents import SourceRef
from compileit_chat.interface.api.log_config import JsonFormatter, request_id
from compileit_chat.interface.api.rate_limit import SlidingWindowRateLimiter
from compileit_chat.interface.api.sse import encode


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (TokenEvent("Hej på er"), 'event: token\ndata: {"text": "Hej på er"}\n\n'),
        (
            ToolCallEvent("search_website", "AI-tjänster"),
            'event: tool_start\ndata: {"tool": "search_website", "query": "AI-tjänster"}\n\n',
        ),
        (
            SourcesEvent((SourceRef("Om oss", "https://compileit.com/om-oss"),)),
            'event: sources\ndata: {"sources": [{"title": "Om oss", '
            '"url": "https://compileit.com/om-oss"}]}\n\n',
        ),
        (DoneEvent(), "event: done\ndata: {}\n\n"),
        (ErrorEvent("Något gick fel"), 'event: error\ndata: {"message": "Något gick fel"}\n\n'),
    ],
)
def test_sse_encoding(event: object, expected: str) -> None:
    assert encode(event) == expected  # type: ignore[arg-type]


def test_sse_data_with_newlines_stays_on_one_line() -> None:
    assert encode(TokenEvent("rad 1\n\nrad 2")).count("\n") == 3  # event, data, blank line


def test_rate_limiter_allows_again_after_the_window() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(2, window_seconds=10, clock=lambda: now[0])

    assert [limiter.retry_after("a"), limiter.retry_after("a")] == [None, None]
    assert limiter.retry_after("a") == pytest.approx(10)
    assert limiter.retry_after("b") is None  # per client
    now[0] = 10.0
    assert limiter.retry_after("a") is None


def test_json_formatter_includes_request_id_and_extras() -> None:
    record = logging.makeLogRecord(
        {"name": "api", "levelname": "INFO", "msg": "Chat %s", "args": ("request",)}
    )
    record.session_id = "session-1"
    token = request_id.set("req-1")
    try:
        entry = json.loads(JsonFormatter().format(record))
    finally:
        request_id.reset(token)

    assert entry | {"ts": "-"} == {
        "ts": "-",
        "level": "INFO",
        "logger": "api",
        "message": "Chat request",
        "request_id": "req-1",
        "session_id": "session-1",
    }
