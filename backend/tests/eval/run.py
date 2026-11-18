"""`make eval`: run the golden cases through the real stack and write docs/eval-report.md.

Real OpenAI calls (costs a few cents), so it is not part of CI. Each case runs in a fresh
session through `AskQuestion` -> `LangGraphOrchestrator`, exactly as the API does; a thin
`ChatAgentPort` decorator records what the agent retrieved, without touching production code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import time
import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from compileit_chat.application.dto import (
    ErrorEvent,
    RetrievalEvent,
    SourcesEvent,
    TokenEvent,
    ToolCallEvent,
)
from compileit_chat.application.use_cases import AskQuestion
from compileit_chat.config import BACKEND_DIR, Settings
from compileit_chat.container import Container
from compileit_chat.domain.conversation import Question, SessionId
from tests.eval.judge import Judge
from tests.eval.metrics import CaseResult, load_cases, summarise
from tests.eval.report import render, with_results

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from compileit_chat.application.dto import AgentEvent
    from compileit_chat.application.ports import ChatAgentPort
    from tests.eval.metrics import GoldenCase

REPORT_PATH = BACKEND_DIR.parent / "docs" / "eval-report.md"
RESULTS_DIR = BACKEND_DIR / "data" / "runtime" / "eval"
MAX_SOURCE_CHARS = 8_000  # per page, for the judge


class RecordingAgent:
    """`ChatAgentPort` decorator recording tool calls, retrieved pages and time to first token."""

    def __init__(self, inner: ChatAgentPort) -> None:
        self._inner = inner
        self.tools: list[tuple[str, str | None]] = []
        self.retrieved: list[str] = []

    async def stream(self, session_id: SessionId, question: Question) -> AsyncIterator[AgentEvent]:
        async for event in self._inner.stream(session_id, question):
            match event:
                case ToolCallEvent(tool=tool, query=query):
                    self.tools.append((tool, query))
                case RetrievalEvent(sources=sources):
                    self.retrieved += [s.url for s in sources if s.url not in self.retrieved]
            yield event


async def run_case(
    case: GoldenCase, container: Container, agent: ChatAgentPort, judge: Judge
) -> CaseResult:
    session = SessionId(f"eval-{case.id}-{uuid.uuid4().hex[:8]}")
    result = CaseResult(case=case)
    conversation: list[str] = []
    for index, question in enumerate(case.turns):
        recorder = RecordingAgent(agent)  # only the last turn's activity is scored
        answer, started = [], time.perf_counter()
        result.first_token_s, result.error, result.cited = None, None, []
        async for event in AskQuestion(recorder).execute(session, Question(question)):
            match event:
                case TokenEvent(text=text):
                    result.first_token_s = result.first_token_s or time.perf_counter() - started
                    answer.append(text)
                case SourcesEvent(sources=sources):
                    result.cited = [s.url for s in sources]
                case ErrorEvent(message=message):
                    result.error = message
        result.answer, result.total_s = "".join(answer), time.perf_counter() - started
        result.tools, result.retrieved = recorder.tools, recorder.retrieved
        if index < len(case.turns) - 1:
            conversation.append(f"User: {question}\nBot: {result.answer}")

    if len(case.turns) == 1 and case.kind != "out_of_scope":
        hits = await container.retriever.search(case.turns[0], 5)
        result.raw_top5 = [hit.chunk.document_url for hit in hits]

    result.verdict = await judge.assess(
        case, "\n\n".join(conversation), result.answer, await _sources_text(container, result)
    )
    status = "PASS" if result.passed else "FAIL"
    print(f"  {status}  {case.id:<20} faithfulness={result.verdict.faithfulness}", flush=True)
    return result


async def _sources_text(container: Container, result: CaseResult) -> str:
    pages = []
    for url in result.retrieved:
        document = await container.document_store.get(url)
        if document:
            pages.append(
                f'<page url="{url}" title="{document.title}">\n'
                f"{document.text[:MAX_SOURCE_CHARS]}\n</page>"
            )
    return "\n\n".join(pages)


async def main(case_ids: list[str], concurrency: int, judge_model: str) -> None:
    settings = Settings()
    container = Container(settings)
    await container.prepare()  # build the index from the snapshot if it is missing
    if settings.openai_api_key is None:
        raise SystemExit("OPENAI_API_KEY is not set.")
    judge = Judge(judge_model, settings.openai_api_key)
    cases = [c for c in load_cases() if not case_ids or c.id in case_ids]

    print(f"Running {len(cases)} cases (concurrency {concurrency})...")
    started = time.perf_counter()
    limit = asyncio.Semaphore(concurrency)
    async with container.orchestrator() as agent:

        async def bounded(case: GoldenCase) -> CaseResult:
            async with limit:
                return await run_case(case, container, agent, judge)

        results = await asyncio.gather(*(bounded(case) for case in cases))

    run_info = {
        "Date": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "Commit": _git_commit(),
        "Chat model": f"`{settings.chat_model}` (temperature {settings.chat_temperature})",
        "Embedding model": f"`{settings.embedding_model}`",
        "Judge model": f"`{judge_model}`",
        "Cases": str(len(results)),
        "Corpus": f"{len(await container.document_store.list_all())} pages (committed snapshot)",
        "Wall time": f"{time.perf_counter() - started:.0f} s",
    }
    _write(results, run_info, update_report=not case_ids)
    print()
    for metric in summarise(results):
        print(f"{metric.name:<40} {metric.value}")


def _write(results: list[CaseResult], run_info: dict[str, str], *, update_report: bool) -> None:
    if update_report:
        REPORT_PATH.write_text(
            with_results(REPORT_PATH.read_text(encoding="utf-8"), render(results, run_info)),
            encoding="utf-8",
            newline="\n",
        )
        print(f"\nReport: {REPORT_PATH}")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    raw = RESULTS_DIR / f"{datetime.now(UTC):%Y%m%d-%H%M%S}.json"
    raw.write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Raw results: {raw}")


def _git_commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = subprocess.run(["git", "diff", "--quiet"], check=False).returncode != 0
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return f"`{sha}`" + (" (with uncommitted changes)" if dirty else "")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cases", nargs="*", help="Only these case ids (report is not written).")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--judge-model", default="gpt-4.1")
    args = parser.parse_args()
    asyncio.run(main(args.cases, args.concurrency, args.judge_model))
