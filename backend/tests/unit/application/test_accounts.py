from datetime import timedelta

import pytest

from compileit_chat.application.errors import AuthenticationError, UserExistsError
from compileit_chat.application.use_cases import Authenticate, CreateUser, Login, Logout
from compileit_chat.application.use_cases.accounts import hash_token
from compileit_chat.domain.errors import WeakPasswordError
from tests.fakes import (
    FixedClock,
    InMemoryAuthSessions,
    InMemoryUserRepository,
    LoginEventRecorder,
    PlainTextHasher,
)

PASSWORD = "ett-langt-losenord"


class Accounts:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.sessions = InMemoryAuthSessions()
        self.events = LoginEventRecorder()
        self.clock = FixedClock()
        hasher = PlainTextHasher()
        self.create = CreateUser(self.users, hasher, self.clock)
        self.login = Login(
            self.users, hasher, self.sessions, self.events, self.clock, timedelta(hours=1)
        )
        self.logout = Logout(self.sessions)
        self.authenticate = Authenticate(self.sessions, self.users, self.clock)


@pytest.fixture
def accounts() -> Accounts:
    return Accounts()


async def test_created_user_has_hashed_password(accounts: Accounts) -> None:
    user = await accounts.create.execute("Anna", PASSWORD)

    assert user.username.value == "anna"
    assert user.password_hash == f"hashed:{PASSWORD}"
    assert PASSWORD not in repr(user.username)


async def test_create_user_enforces_rules_and_uniqueness(accounts: Accounts) -> None:
    await accounts.create.execute("anna", PASSWORD)

    with pytest.raises(UserExistsError):
        await accounts.create.execute("ANNA", "ett-helt-nytt-losenord")
    with pytest.raises(WeakPasswordError):
        await accounts.create.execute("bertil", "kort")


async def test_login_opens_a_session_storing_only_the_token_hash(accounts: Accounts) -> None:
    user = await accounts.create.execute("anna", PASSWORD)

    result = await accounts.login.execute(" Anna ", PASSWORD, "10.0.0.1")

    assert result.user == user
    assert result.expires_at == accounts.clock.current + timedelta(hours=1)
    assert list(accounts.sessions.sessions) == [hash_token(result.token)]
    assert result.token not in accounts.sessions.sessions
    assert await accounts.authenticate.execute(result.token) == user
    assert accounts.events.events == [("Anna", True, "10.0.0.1")]


@pytest.mark.parametrize(
    ("username", "password"), [("anna", "fel-losenord!"), ("okand", PASSWORD), ("!!", PASSWORD)]
)
async def test_failed_logins_are_indistinguishable_and_recorded(
    accounts: Accounts, username: str, password: str
) -> None:
    await accounts.create.execute("anna", PASSWORD)

    with pytest.raises(AuthenticationError, match="Fel användarnamn eller lösenord"):
        await accounts.login.execute(username, password, None)

    assert accounts.events.events == [(username, False, None)]
    assert accounts.sessions.sessions == {}


async def test_sessions_expire_and_end_at_logout(accounts: Accounts) -> None:
    await accounts.create.execute("anna", PASSWORD)
    result = await accounts.login.execute("anna", PASSWORD, None)

    accounts.clock.current += timedelta(hours=2)
    assert await accounts.authenticate.execute(result.token) is None

    accounts.clock.current -= timedelta(hours=2)
    await accounts.logout.execute(result.token)
    assert await accounts.authenticate.execute(result.token) is None


async def test_unknown_or_missing_token_is_anonymous(accounts: Accounts) -> None:
    assert await accounts.authenticate.execute(None) is None
    assert await accounts.authenticate.execute("not-a-token") is None
