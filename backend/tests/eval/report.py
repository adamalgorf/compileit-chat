"""Render eval results as markdown, inside the generated block of docs/eval-report.md."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from tests.eval.metrics import summarise

if TYPE_CHECKING:
    from tests.eval.metrics import CaseResult

START = "<!-- generated:eval:start -->"
END = "<!-- generated:eval:end -->"
_BLOCK = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)


def render(results: list[CaseResult], run_info: dict[str, str]) -> str:
    lines = [START, "", "### Run", ""]
    lines += [f"- **{key}**: {value}" for key, value in run_info.items()]
    lines += ["", "### Summary", "", "| Metric | Result | Definition |", "|---|---|---|"]
    lines += [f"| {m.name} | **{m.value}** | {m.detail} |" for m in summarise(results)]
    lines += [
        "",
        "### Per case",
        "",
        "| Case | Kind | Pass | Retriever@5 | Agent hit | Cited | Faithful | Tools | 1st token |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        tools = ", ".join(f"{t}({q!r})" if q else t for t, q in r.tools) or "-"
        lines.append(
            f"| `{r.case.id}` | {r.case.kind} | {_mark(r.passed)} | {_mark(r.raw_hit)} "
            f"| {_mark(r.agent_hit)} | {_mark(r.cited_expected)} "
            f"| {r.verdict.faithfulness if r.verdict else '-'} | {_cell(tools)} "
            f"| {f'{r.first_token_s:.1f} s' if r.first_token_s else '-'} |"
        )
    failures = [r for r in results if not r.passed]
    lines += ["", "### Failures", ""]
    if not failures:
        lines.append("None.")
    for r in failures:
        lines += [
            f"#### `{r.case.id}`",
            "",
            f"- **Question:** {' → '.join(r.case.turns)}",
            f"- **Judge:** {r.verdict.explanation if r.verdict else r.error}",
        ]
        if r.verdict and r.verdict.unsupported_claims:
            lines.append(f"- **Unsupported claims:** {'; '.join(r.verdict.unsupported_claims)}")
        lines += [f"- **Cited:** {', '.join(r.cited) or '-'}", "", _quote(r.answer), ""]
    lines.append(END)
    return "\n".join(lines)


def with_results(document: str, block: str) -> str:
    if not _BLOCK.search(document):
        raise ValueError(f"Markers {START} ... {END} not found.")
    return _BLOCK.sub(lambda _: block, document)


def _mark(value: bool | None) -> str:
    return {True: "✅", False: "❌", None: "-"}[value]


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in (text or "(no answer)").splitlines())
