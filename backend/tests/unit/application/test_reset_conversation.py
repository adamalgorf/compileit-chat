from compileit_chat.application.use_cases import ResetConversation
from compileit_chat.domain.conversation import SessionId
from tests.fakes import InMemoryConversationStore


async def test_reset_forgets_only_that_session() -> None:
    kept, reset = SessionId("session-keep"), SessionId("session-reset")
    store = InMemoryConversationStore({kept, reset})

    await ResetConversation(store).execute(reset)

    assert store.sessions == {kept}


async def test_reset_of_unknown_session_is_noop() -> None:
    store = InMemoryConversationStore()

    await ResetConversation(store).execute(SessionId("session-unknown"))

    assert store.sessions == set()
