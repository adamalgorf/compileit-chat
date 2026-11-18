"""HTTP-level tests: FastAPI app, auth cookie, SSE and history, against in-memory fakes and
against the real LangGraph graph."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager, contextmanager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from compileit_chat.application.dto import RetrievalEvent, TokenEvent, ToolCallEvent
from compileit_chat.application.use_cases import (
    AskQuestion,
    Authenticate,
    ChatWithHistory,
    CreateUser,
    DeleteConversation,
    GetConversation,
    ListConversations,
    Login,
    Logout,
)
from compileit_chat.application.use_cases.ask_question import AGENT_ERROR_MESSAGE
from compileit_chat.container import AppUseCases
from compileit_chat.domain.conversation import SessionId
from compileit_chat.domain.documents import SourceRef
from compileit_chat.interface.api.app import ApiConfig, create_app
from compileit_chat.interface.api.routes import (
    LOGIN_RATE_LIMITED_MESSAGE,
    NOT_LOGGED_IN_MESSAGE,
    RATE_LIMITED_MESSAGE,
)
from tests.agent_factory import CONTACT, CONTACT_ANSWER, contact_turn, make_orchestrator
from tests.fakes import (
    ApiCallRecorder,
    FixedClock,
    InMemoryAuthSessions,
    InMemoryConversations,
    InMemoryConversationStore,
    InMemoryUserRepository,
    LoginEventRecorder,
    PlainTextHasher,
    ScriptedAgent,
)
from tests.scripted_chat_model import ScriptedChatModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from compileit_chat.application.ports import ChatAgentPort

CONVERSATION = "conversation-0001"
PASSWORD = "ett-langt-losenord"
SOURCE = SourceRef("Kontakta oss", "https://compileit.com/kontakt")
SCRIPT = [
    ToolCallEvent(tool="search_website", query="kontakt"),
    RetrievalEvent(sources=(SOURCE,)),
    TokenEvent("Mejla oss, se "),
    TokenEvent(f"[Kontakta oss]({SOURCE.url})."),
]


class FakeBackend:
    """The real use cases over in-memory adapters, with users 'anna' and 'bertil'."""

    def __init__(self, agent: ChatAgentPort) -> None:
        # Real time: the cookie's expiry is checked against the actual clock by the client.
        clock, hasher = FixedClock(datetime.now(UTC)), PlainTextHasher()
        self.users, self.sessions = InMemoryUserRepository(), InMemoryAuthSessions()
        self.login_events, self.api_log = LoginEventRecorder(), ApiCallRecorder()
        self.conversations, self.memory = InMemoryConversations(), InMemoryConversationStore()
        self.create_user = CreateUser(self.users, hasher, clock)
        self._use_cases = AppUseCases(
            chat=ChatWithHistory(AskQuestion(agent), self.conversations, self.api_log, clock),
            list_conversations=ListConversations(self.conversations),
            get_conversation=GetConversation(self.conversations),
            delete_conversation=DeleteConversation(self.conversations, self.memory),
            login=Login(
                self.users, hasher, self.sessions, self.login_events, clock, timedelta(hours=1)
            ),
            logout=Logout(self.sessions),
            authenticate=Authenticate(self.sessions, self.users, clock),
        )
        self.lifecycle: list[str] = []

    @asynccontextmanager
    async def use_cases(self) -> AsyncIterator[AppUseCases]:
        yield self._use_cases

    async def prepare(self) -> None:
        self.lifecycle.append("prepare")
        for name in ("anna", "bertil"):
            await self.create_user.execute(name, PASSWORD)

    async def stop(self) -> None:
        self.lifecycle.append("stop")


@contextmanager
def api(
    agent: ChatAgentPort | None = None, config: ApiConfig | None = None
) -> Iterator[tuple[TestClient, FakeBackend]]:
    backend = FakeBackend(agent or ScriptedAgent(SCRIPT))
    with TestClient(create_app(backend, config or ApiConfig())) as client:  # runs lifespan
        yield client, backend
    assert backend.lifecycle == ["prepare", "stop"]


@pytest.fixture
def client() -> Iterator[TestClient]:
    with api() as (test_client, _):
        login(test_client)
        yield test_client


def login(client: TestClient, username: str = "anna", password: str = PASSWORD) -> Any:
    client.cookies.clear()
    return client.post("/api/auth/login", json={"username": username, "password": password})


def ask(
    client: TestClient, message: str = "Hur kontaktar man er?", conversation: str = CONVERSATION
) -> Any:
    return client.post("/api/chat", json={"conversation_id": conversation, "message": message})


def parse_sse(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


# --- auth --------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/chat"),
        ("GET", "/api/conversations"),
        ("GET", "/api/auth/me"),
        ("GET", f"/api/conversations/{CONVERSATION}"),
        ("DELETE", f"/api/conversations/{CONVERSATION}"),
    ],
)
def test_everything_but_login_and_health_requires_a_session(method: str, path: str) -> None:
    with api() as (client, _):
        response = client.request(
            method, path, json={"conversation_id": CONVERSATION, "message": "Hej"}
        )

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_LOGGED_IN_MESSAGE}


def test_login_sets_a_hardened_session_cookie_and_logout_ends_it() -> None:
    with api() as (client, backend):
        response = login(client, " Anna ")
        cookie = response.headers["set-cookie"].lower()
        me = client.get("/api/auth/me").json()
        client.post("/api/auth/logout")
        after_logout = client.get("/api/auth/me").status_code

    assert response.json() == {"username": "anna"}
    assert "compileit_session=" in cookie
    for flag in ("httponly", "samesite=lax", "path=/api", "expires="):
        assert flag in cookie
    assert "secure" not in cookie  # plain-http dev default; ApiConfig(cookie_secure=True)
    assert me == {"username": "anna"}
    assert after_logout == 401
    assert backend.sessions.sessions == {}


@pytest.mark.parametrize(("username", "password"), [("anna", "fel-losenord"), ("okand", PASSWORD)])
def test_failed_login_does_not_reveal_which_part_was_wrong(username: str, password: str) -> None:
    with api() as (client, backend):
        response = login(client, username, password)

    assert response.status_code == 401
    assert response.json() == {"detail": "Fel användarnamn eller lösenord."}
    assert "set-cookie" not in response.headers
    assert backend.login_events.events[-1][:2] == (username, False)


def test_login_attempts_are_rate_limited_per_client() -> None:
    config = ApiConfig(login_attempts=2, login_window_seconds=60)
    with api(config=config) as (client, _):
        statuses = [login(client, "anna", "fel").status_code for _ in range(3)]
        limited = login(client)

    assert statuses == [401, 401, 429]
    assert limited.json() == {"detail": LOGIN_RATE_LIMITED_MESSAGE}


# --- chat and history --------------------------------------------------------------------


def test_chat_streams_events_and_saves_the_conversation(client: TestClient) -> None:
    response = ask(client)
    listed = client.get("/api/conversations").json()
    opened = client.get(f"/api/conversations/{CONVERSATION}").json()

    assert response.headers["content-type"].startswith("text/event-stream")
    assert parse_sse(response.text) == [
        ("tool_start", {"tool": "search_website", "query": "kontakt"}),
        ("token", {"text": "Mejla oss, se "}),
        ("token", {"text": f"[Kontakta oss]({SOURCE.url})."}),
        ("sources", {"sources": [{"title": SOURCE.title, "url": SOURCE.url}]}),
        ("done", {}),
    ]
    assert [(c["id"], c["title"]) for c in listed] == [(CONVERSATION, "Hur kontaktar man er?")]
    user_message, answer = opened["messages"]
    assert (user_message["role"], user_message["content"]) == ("user", "Hur kontaktar man er?")
    assert answer["role"] == "assistant"
    assert answer["status"] == "done"
    assert answer["sources"] == [{"title": SOURCE.title, "url": SOURCE.url}]


def test_users_cannot_see_or_touch_each_others_conversations() -> None:
    with api() as (client, _):
        login(client, "anna")
        ask(client)
        login(client, "bertil")

        assert client.get("/api/conversations").json() == []
        assert client.get(f"/api/conversations/{CONVERSATION}").status_code == 404
        assert client.delete(f"/api/conversations/{CONVERSATION}").status_code == 404
        assert ask(client).status_code == 404  # cannot continue it either

        login(client, "anna")
        assert len(client.get("/api/conversations").json()) == 1


def test_delete_conversation_removes_history_and_agent_memory() -> None:
    with api() as (client, backend):
        login(client)
        ask(client)
        backend.memory.sessions.add(SessionId(CONVERSATION))

        deleted = client.delete(f"/api/conversations/{CONVERSATION}")
        reopened = client.get(f"/api/conversations/{CONVERSATION}")

    assert deleted.status_code == 204
    assert reopened.status_code == 404
    assert backend.memory.sessions == set()
    assert len(backend.api_log.calls) == 1  # the audit record stays


@pytest.mark.parametrize(
    "body",
    [
        {"conversation_id": CONVERSATION, "message": ""},
        {"conversation_id": CONVERSATION, "message": "   "},  # passes schema, fails domain
        {"conversation_id": "bad id with spaces", "message": "Hej"},
        {"conversation_id": CONVERSATION},
        {"conversation_id": CONVERSATION, "message": "x" * 2001},
    ],
)
def test_invalid_chat_requests_are_rejected_before_streaming(
    client: TestClient, body: dict[str, str]
) -> None:
    response = client.post("/api/chat", json=body)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/json"
    assert client.get("/api/conversations").json() == []  # nothing saved


def test_agent_failure_ends_stream_with_error_and_is_saved() -> None:
    with api(ScriptedAgent([TokenEvent("Vi ")], fail=True)) as (client, backend):
        login(client)
        events = parse_sse(ask(client).text)
        answer = client.get(f"/api/conversations/{CONVERSATION}").json()["messages"][1]

    assert events == [("token", {"text": "Vi "}), ("error", {"message": AGENT_ERROR_MESSAGE})]
    assert (answer["status"], answer["content"]) == ("error", AGENT_ERROR_MESSAGE)
    assert backend.api_log.calls[0].status == "error"


def test_chat_is_rate_limited_per_user() -> None:
    config = ApiConfig(rate_limit_requests=2, rate_limit_window_seconds=60)
    with api(config=config) as (client, _):
        login(client, "anna")
        statuses = [ask(client).status_code for _ in range(3)]
        limited = ask(client)
        login(client, "bertil")
        other_user = ask(client, conversation="conversation-0002").status_code

    assert statuses == [200, 200, 429]
    assert limited.json() == {"detail": RATE_LIMITED_MESSAGE}
    assert other_user == 200


# --- cross-cutting -----------------------------------------------------------------------


def test_cors_allows_credentials_from_the_frontend_origin_only(client: TestClient) -> None:
    preflight = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }

    allowed = client.options("/api/chat", headers=preflight)
    denied = client.options("/api/chat", headers={**preflight, "Origin": "https://evil.example"})

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in denied.headers


def test_health_and_request_id() -> None:
    with api() as (client, _):
        response = client.get("/api/health", headers={"X-Request-ID": "abc-123"})

    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "abc-123"


def test_full_stack_with_real_graph_and_scripted_model() -> None:
    """HTTP → auth → ChatWithHistory → AskQuestion → real LangGraph graph → tools."""
    model = ScriptedChatModel(replies=[*contact_turn(), *contact_turn()])
    with api(make_orchestrator(model)) as (client, _):
        login(client)
        first = parse_sse(ask(client).text)
        ask(client, "Och var sitter ni?")
        saved = client.get(f"/api/conversations/{CONVERSATION}").json()["messages"]

    assert first[0] == ("tool_start", {"tool": "search_website", "query": "kontakt"})
    assert "".join(data["text"] for name, data in first if name == "token") == CONTACT_ANSWER
    assert first[-2:] == [
        ("sources", {"sources": [{"title": CONTACT.title, "url": CONTACT.url}]}),
        ("done", {}),
    ]
    assert [m["role"] for m in saved] == ["user", "assistant", "user", "assistant"]
    follow_up_prompt = model.received[2]  # first model call of the second turn
    assert "Hur kontaktar man er?" in [m.content for m in follow_up_prompt]
