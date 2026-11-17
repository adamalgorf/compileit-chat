import pytest

from compileit_chat.domain.documents import SourceRef
from compileit_chat.domain.sources import cited_sources, normalize_url, unique_sources

ABOUT = SourceRef("Om oss", "https://www.compileit.com/om-oss")
CONTACT = SourceRef("Kontakt", "https://www.compileit.com/kontakt")


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.compileit.com/om-oss/", "https://www.compileit.com/om-oss"),
        ("HTTPS://WWW.Compileit.com/om-oss", "https://www.compileit.com/om-oss"),
        ("https://www.compileit.com/om-oss#team", "https://www.compileit.com/om-oss"),
        ("https://www.compileit.com/", "https://www.compileit.com"),
        ("https://www.compileit.com/sok?q=ai", "https://www.compileit.com/sok?q=ai"),
    ],
)
def test_normalize_url(url: str, expected: str) -> None:
    assert normalize_url(url) == expected


def test_unique_sources_keeps_first_occurrence_and_order() -> None:
    duplicate = SourceRef("Om oss (dup)", "https://www.compileit.com/om-oss/#x")

    assert unique_sources([ABOUT, CONTACT, duplicate]) == (ABOUT, CONTACT)


def test_cited_sources_returns_only_linked_candidates() -> None:
    answer = f"Vi finns i Stockholm ([Kontakt]({CONTACT.url}/))."

    assert cited_sources(answer, [ABOUT, CONTACT]) == (CONTACT,)


def test_cited_sources_ignores_trailing_punctuation_and_bare_urls() -> None:
    answer = f"Läs mer på {ABOUT.url}."

    assert cited_sources(answer, [ABOUT]) == (ABOUT,)


def test_cited_sources_is_empty_for_answers_without_links() -> None:
    answer = "Det hittar jag inte på compileit.com."

    assert cited_sources(answer, [ABOUT, CONTACT]) == ()


def test_cited_sources_never_invents_sources_that_were_not_retrieved() -> None:
    answer = "Se [Tesla](https://www.tesla.com)."

    assert cited_sources(answer, [ABOUT]) == ()
