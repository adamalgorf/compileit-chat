import pytest

from compileit_chat.domain.accounts import (
    MIN_PASSWORD_LENGTH,
    Username,
    validate_new_password,
)
from compileit_chat.domain.conversation import Question
from compileit_chat.domain.errors import InvalidUsernameError, WeakPasswordError
from compileit_chat.domain.history import TITLE_LENGTH, conversation_title


def test_username_is_normalised() -> None:
    assert Username("  Anna.S ").value == "anna.s"


@pytest.mark.parametrize("value", ["ab", "-anna", "anna svensson", "anna@x.se", "a" * 65, ""])
def test_username_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidUsernameError):
        Username(value)


def test_password_rules() -> None:
    validate_new_password("x" * MIN_PASSWORD_LENGTH, Username("anna"))
    with pytest.raises(WeakPasswordError):
        validate_new_password("x" * (MIN_PASSWORD_LENGTH - 1), Username("anna"))
    with pytest.raises(WeakPasswordError, match="användarnamnet"):
        validate_new_password("mitt-ANNA-losenord", Username("anna"))


def test_short_question_is_its_own_title() -> None:
    assert conversation_title(Question("  Vilka  branscher? ")) == "Vilka branscher?"


def test_long_question_is_cut_at_a_word_boundary() -> None:
    title = conversation_title(Question("Berätta " * 20))

    assert title.endswith("…")
    assert len(title) <= TITLE_LENGTH + 1
    assert not title.removesuffix("…").endswith(" ")
