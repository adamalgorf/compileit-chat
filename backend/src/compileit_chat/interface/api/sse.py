"""Serialise application chat events as Server-Sent Events.

This is the wire contract the frontend's `useChatStream` parses; the union of event names
and payloads is mirrored in `frontend/lib/types.ts`.

    event: token       data: {"text": "..."}
    event: tool_start  data: {"tool": "search_website", "query": "..."}
    event: sources     data: {"sources": [{"title": "...", "url": "..."}]}
    event: done        data: {}
    event: error       data: {"message": "..."}
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from compileit_chat.application.dto import (
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)

if TYPE_CHECKING:
    from compileit_chat.application.dto import ChatEvent


def encode(event: ChatEvent) -> str:
    name, data = _wire(event)
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _wire(event: ChatEvent) -> tuple[str, dict[str, Any]]:
    match event:
        case TokenEvent(text=text):
            return "token", {"text": text}
        case ToolCallEvent(tool=tool, query=query):
            return "tool_start", {"tool": tool, "query": query}
        case SourcesEvent(sources=sources):
            return "sources", {"sources": [{"title": s.title, "url": s.url} for s in sources]}
        case DoneEvent():
            return "done", {}
        case ErrorEvent(message=message):
            return "error", {"message": message}
