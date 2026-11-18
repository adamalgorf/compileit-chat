"""Golden cases, per-case results and the scoring rules. Pure: no I/O, no models."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import yaml

type Kind = Literal["answerable", "not_on_site", "out_of_scope"]

GOLDEN_PATH = Path(__file__).with_name("golden.yaml")
MIN_FAITHFULNESS = 4  # on the judge's 1-5 scale


@dataclass(frozen=True)
class GoldenCase:
    id: str
    kind: Kind
    turns: list[str]
    expected_pages: list[str]
    facts: str


def load_cases(path: Path = GOLDEN_PATH) -> list[GoldenCase]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [GoldenCase(**case) for case in data["cases"]]


@dataclass(frozen=True)
class Verdict:
    """The judge's assessment of one answer."""

    faithfulness: int  # 1-5: are the answer's claims supported by the pages the agent read?
    correct_behaviour: bool  # kind-specific: answered / said "not found" / refused
    unsupported_claims: list[str]
    explanation: str


@dataclass
class CaseResult:
    case: GoldenCase
    answer: str = ""
    tools: list[tuple[str, str | None]] = field(default_factory=list)
    retrieved: list[str] = field(default_factory=list)  # pages the agent's tools returned
    cited: list[str] = field(default_factory=list)  # pages the final answer links to
    raw_top5: list[str] | None = None  # retriever alone, single-turn cases only
    first_token_s: float | None = None
    total_s: float = 0.0
    error: str | None = None
    verdict: Verdict | None = None

    # --- per-case metrics ------------------------------------------------------------

    @property
    def raw_hit(self) -> bool | None:
        if self.raw_top5 is None or not self.case.expected_pages:
            return None
        return any(matches(url, self.case.expected_pages) for url in self.raw_top5)

    @property
    def agent_hit(self) -> bool | None:
        if not self.case.expected_pages or self.case.kind == "out_of_scope":
            return None
        return any(matches(url, self.case.expected_pages) for url in self.retrieved)

    @property
    def cited_expected(self) -> bool | None:
        if self.case.kind != "answerable":
            return None
        return any(matches(url, self.case.expected_pages) for url in self.cited)

    @property
    def says_not_found(self) -> bool:
        return "hittar jag inte" in self.answer.casefold()

    @property
    def passed(self) -> bool:
        v = self.verdict
        if self.error or v is None:
            return False
        faithful = v.faithfulness >= MIN_FAITHFULNESS
        match self.case.kind:
            case "answerable":
                return bool(
                    self.agent_hit
                    and self.cited
                    and not self.says_not_found
                    and faithful
                    and v.correct_behaviour
                )
            case "not_on_site":
                return faithful and v.correct_behaviour
            case "out_of_scope":
                # Searching first is by design (every turn starts with a tool call), so only
                # the outcome counts: a refusal that cites nothing.
                return v.correct_behaviour and not self.cited


def matches(url: str, expected_paths: list[str]) -> bool:
    """`/uppdrag` matches `/uppdrag` and `/uppdrag/balder`, not `/uppdragsgivare`."""
    path = urlsplit(url).path.rstrip("/") or "/"
    return any(
        path == expected.rstrip("/") or path.startswith(expected.rstrip("/") + "/")
        for expected in expected_paths
    )


# --- aggregate -------------------------------------------------------------------------


@dataclass(frozen=True)
class Metric:
    name: str
    value: str
    detail: str


def summarise(results: list[CaseResult]) -> list[Metric]:
    answerable = [r for r in results if r.case.kind == "answerable"]
    not_on_site = [r for r in results if r.case.kind == "not_on_site"]
    out_of_scope = [r for r in results if r.case.kind == "out_of_scope"]
    verdicts = [r.verdict for r in results if r.verdict]
    first_tokens = [r.first_token_s for r in results if r.first_token_s is not None]

    return [
        _rate("Overall pass rate", [r.passed for r in results], "all criteria for the kind met"),
        _rate(
            "Retrieval hit rate (retriever, top 5)",
            [r.raw_hit for r in results],
            "expected page in the hybrid retriever's top 5 for the raw question",
        ),
        _rate(
            "Retrieval hit rate (agent)",
            [r.agent_hit for r in results],
            "expected page among the pages the agent's tool calls returned",
        ),
        _rate(
            "Citation presence",
            [bool(r.cited) for r in answerable],
            "answerable questions whose answer links at least one source",
        ),
        _rate(
            "Expected source cited",
            [r.cited_expected for r in answerable],
            "answerable questions citing an expected page",
        ),
        _rate(
            "Refusal correctness (out of scope)",
            [r.passed for r in out_of_scope],
            "politely refused, cited nothing, no prompt leak",
        ),
        _rate(
            "'Not found' correctness",
            [r.passed for r in not_on_site],
            "said the site does not answer it, invented nothing",
        ),
        _rate(
            "No false 'not found'",
            [not r.says_not_found for r in answerable],
            "answerable questions not wrongly answered with 'hittar jag inte'",
        ),
        Metric(
            "Faithfulness (judge, 1-5)",
            f"{statistics.mean(v.faithfulness for v in verdicts):.2f}" if verdicts else "-",
            f"mean; min {min(v.faithfulness for v in verdicts)}" if verdicts else "",
        ),
        Metric(
            "Latency to first token",
            f"{statistics.median(first_tokens):.1f} s" if first_tokens else "-",
            f"median; max {max(first_tokens):.1f} s" if first_tokens else "",
        ),
    ]


def _rate(name: str, outcomes: list[bool | None], detail: str) -> Metric:
    counted = [o for o in outcomes if o is not None]
    if not counted:
        return Metric(name, "-", detail)
    hits = sum(counted)
    return Metric(name, f"{hits}/{len(counted)} ({hits / len(counted):.0%})", detail)
