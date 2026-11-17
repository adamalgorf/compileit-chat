import pytest

from compileit_chat.domain.conversation import MAX_QUESTION_LENGTH, Question, SessionId
from compileit_chat.domain.errors import InvalidQuestionError, InvalidSessionIdError


def test_session_id_accepts_uuid() -> None:
    value = "3f2b8c1e-4a5d-4e6f-9a7b-1c2d3e4f5a6b"

    assert str(SessionId(value)) == value


@pytest.mark.parametrize("value", ["", "short", "has space in it", "../../etc/passwd", "x" * 129])
def test_session_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidSessionIdError):
        SessionId(value)


def test_question_is_stripped() -> None:
    assert Question("  Vilka branscher jobbar ni med?\n").text == "Vilka branscher jobbar ni med?"


@pytest.mark.parametrize("text", ["", "   \n\t"])
def test_question_rejects_blank_text(text: str) -> None:
    with pytest.raises(InvalidQuestionError):
        Question(text)


def test_question_rejects_overlong_text() -> None:
    with pytest.raises(InvalidQuestionError):
        Question("a" * (MAX_QUESTION_LENGTH + 1))


def test_question_length_limit_applies_after_stripping() -> None:
    assert Question(" " + "a" * MAX_QUESTION_LENGTH + " ").text == "a" * MAX_QUESTION_LENGTH
