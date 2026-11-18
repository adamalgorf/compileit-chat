"""The eval's scoring rules are code too: test them without any model calls."""

import pytest

from tests.eval.metrics import (
    CaseResult,
    GoldenCase,
    Kind,
    Verdict,
    load_cases,
    matches,
    summarise,
)
from tests.eval.report import END, START, render, with_results

GOOD = Verdict(faithfulness=5, correct_behaviour=True, unsupported_claims=[], explanation="ok")


def case(kind: Kind = "answerable", expected: list[str] | None = None) -> GoldenCase:
    return GoldenCase(
        id="c",
        kind=kind,
        turns=["Fråga?"],
        expected_pages=expected or [],
        facts="",
    )


def test_golden_set_is_well_formed() -> None:
    cases = load_cases()

    assert len({c.id for c in cases}) == len(cases)
    assert {c.kind for c in cases} == {"answerable", "not_on_site", "out_of_scope"}
    assert all(c.expected_pages for c in cases if c.kind == "answerable")
    assert sum(c.kind == "out_of_scope" for c in cases) >= 3
    assert any(len(c.turns) > 1 for c in cases)  # follow-ups are covered


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://compileit.com/uppdrag", True),
        ("https://compileit.com/uppdrag/balder/", True),
        ("https://compileit.com/uppdragsgivare", False),
        ("https://compileit.com/kontakt", False),
    ],
)
def test_matches_page_and_sub_pages(url: str, expected: bool) -> None:
    assert matches(url, ["/uppdrag"]) is expected


def test_answerable_passes_only_with_retrieval_citation_and_faithful_answer() -> None:
    good = CaseResult(
        case=case(expected=["/kontakt"]),
        answer="Mejla oss.",
        retrieved=["https://compileit.com/kontakt"],
        cited=["https://compileit.com/kontakt"],
        verdict=GOOD,
    )

    assert good.passed
    assert not CaseResult(**{**good.__dict__, "cited": []}).passed
    assert not CaseResult(**{**good.__dict__, "answer": "Det hittar jag inte."}).passed
    unfaithful = Verdict(3, True, ["påhittad siffra"], "x")
    assert not CaseResult(**{**good.__dict__, "verdict": unfaithful}).passed


def test_out_of_scope_must_refuse_and_cite_nothing() -> None:
    refused = CaseResult(
        case=case("out_of_scope"), answer="Det kan jag inte svara på.", verdict=GOOD
    )

    assert refused.passed
    assert CaseResult(**{**refused.__dict__, "tools": [("search_website", "tesla")]}).passed
    assert not CaseResult(**{**refused.__dict__, "cited": ["https://compileit.com"]}).passed


def test_summary_and_report_render() -> None:
    results = [CaseResult(case=case(expected=["/x"]), raw_top5=["https://c.com/x"], verdict=GOOD)]

    metrics = {m.name: m.value for m in summarise(results)}
    block = render(results, {"Commit": "abc"})

    assert metrics["Retrieval hit rate (retriever, top 5)"] == "1/1 (100%)"
    assert block.startswith(START)
    assert block.endswith(END)
    assert with_results(f"# R\n{START}\nold\n{END}\n", block) == f"# R\n{block}\n"
