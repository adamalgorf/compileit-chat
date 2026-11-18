"""HTTP-level tests: FastAPI app + SSE, against fakes and against the real LangGraph graph."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from compileit_chat.application.dto import RetrievalEvent, TokenEvent, ToolCallEvent
from compileit_chat.application.use_cases import AskQuestion, ResetConversation
from compileit_chat.application.use_cases.ask_question import AGENT_ERROR_MESSAGE
from compileit_chat.container import ChatUseCases
from compileit_chat.domain.conversation import SessionId
from compileit_chat.domain.documents import SourceRef
from compileit_chat.interface.api.app import ApiConfig, create_app
from compileit_chat.interface.api.routes import RATE_LIMITED_MESSAGE
from tests.agent_factory import CONTACT, CONTACT_ANSWER, contact_turn, make_orchestrator
from tests.fakes import InMemoryConversationStore, ScriptedAgent
from tests.scripted_chat_model import ScriptedChatModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from compileit_chat.application.ports import ChatAgentPort, ConversationStorePort

SESSION = "session-0001"
SOURCE = SourceRef("Kontakta oss", "https://compileit.com/kontakt")


class FakeBackend:
    def __init__(self, agent: ChatAgentPort, store: ConversationStorePort) -> None:
        self._use_cases = ChatUseCases(ask=AskQuestion(agent), reset=ResetConversation(store))
        self.prepared = False

    @asynccontextmanager
    async def chat(self) -> AsyncIterator[ChatUseCases]:
        yield self._use_cases

    async def prepare(self) -> None:
        self.prepared = True


@contextmanager
def api_client(
    agent: ChatAgentPort,
    store: ConversationStorePort | None = None,
    config: ApiConfig | None = None,
) -> Iterator[TestClient]:
    backend = FakeBackend(agent, store or InMemoryConversationStore())
    with TestClient(create_app(backend, config or ApiConfig())) as client:  # runs lifespan
        assert backend.prepared
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    script = [
        ToolCallEvent(tool="search_website", query="kontakt"),
        RetrievalEvent(sources=(SOURCE,)),
        TokenEvent("Mejla oss, se "),
        TokenEvent(f"[Kontakta oss]({SOURCE.url})."),
    ]
    with api_client(ScriptedAgent(script)) as test_client:
        yield test_client


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def ask(client: TestClient, message: str, session_id: str = SESSION) -> Any:
    return client.post("/api/chat", json={"session_id": session_id, "message": message})


def test_chat_streams_events_in_contract_order(client: TestClient) -> None:
    response = ask(client, "Hur kontaktar man er?")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(response.text) == [
        ("tool_start", {"tool": "search_website", "query": "kontakt"}),
        ("token", {"text": "Mejla oss, se "}),
        ("token", {"text": f"[Kontakta oss]({SOURCE.url})."}),
        ("sources", {"sources": [{"title": SOURCE.title, "url": SOURCE.url}]}),
        ("done", {}),
    ]


@pytest.mark.parametrize(
    "body",
    [
        {"session_id": SESSION, "message": ""},
        {"session_id": SESSION, "message": "   "},  # passes the schema, fails the domain
        {"session_id": "bad id with spaces", "message": "Hej"},
        {"session_id": SESSION},
        {"session_id": SESSION, "message": "x" * 2001},
    ],
)
def test_invalid_requests_are_rejected_before_streaming(
    client: TestClient, body: dict[str, str]
) -> None:
    response = client.post("/api/chat", json=body)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"


def test_agent_failure_ends_stream_with_error_event() -> None:
    with api_client(ScriptedAgent([TokenEvent("Vi ")], fail=True)) as client:
        events = parse_sse(ask(client, "Hej").text)

    assert events == [("token", {"text": "Vi "}), ("error", {"message": AGENT_ERROR_MESSAGE})]


def test_reset_session() -> None:
    session = SessionId(SESSION)
    store = InMemoryConversationStore({session})
    with api_client(ScriptedAgent([]), store) as client:
        response = client.delete(f"/api/sessions/{SESSION}")

    assert response.status_code == 204
    assert session not in store.sessions


def test_reset_rejects_invalid_session_id(client: TestClient) -> None:
    assert client.delete("/api/sessions/x").status_code == 422


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_request_id_is_echoed_or_generated(client: TestClient) -> None:
    echoed = client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    generated = client.get("/api/health")

    assert echoed.headers["X-Request-ID"] == "abc-123"
    assert len(generated.headers["X-Request-ID"]) == 32


def test_chat_is_rate_limited_per_client() -> None:
    config = ApiConfig(rate_limit_requests=2, rate_limit_window_seconds=60)
    with api_client(ScriptedAgent([]), config=config) as client:
        statuses = [ask(client, "Hej").status_code for _ in range(3)]
        limited = ask(client, "Hej")
        health = client.get("/api/health")

    assert statuses == [200, 200, 429]
    assert limited.json() == {"detail": RATE_LIMITED_MESSAGE}
    assert int(limited.headers["Retry-After"]) >= 1
    assert health.status_code == 200  # only chat is limited


def test_cors_allows_the_configured_frontend_origin(client: TestClient) -> None:
    preflight = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }

    allowed = client.options("/api/chat", headers=preflight)
    denied = client.options("/api/chat", headers={**preflight, "Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "access-control-allow-origin" not in denied.headers


def test_full_stack_with_real_graph_and_scripted_model() -> None:
    """API → AskQuestion → LangGraph agent → tools, with only the LLM scripted."""
    model = ScriptedChatModel(replies=[*contact_turn(), *contact_turn()])
    with api_client(make_orchestrator(model)) as client:
        first = parse_sse(ask(client, "Hur kontaktar man er?").text)
        ask(client, "Och var sitter ni?")

    assert first[0] == ("tool_start", {"tool": "search_website", "query": "kontakt"})
    assert "".join(data["text"] for name, data in first if name == "token") == CONTACT_ANSWER
    assert first[-2:] == [
        ("sources", {"sources": [{"title": CONTACT.title, "url": CONTACT.url}]}),
        ("done", {}),
    ]
    follow_up_prompt = model.received[2]  # first model call of the second turn
    assert "Hur kontaktar man er?" in [m.content for m in follow_up_prompt]
