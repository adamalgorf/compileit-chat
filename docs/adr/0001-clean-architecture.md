# ADR-0001: Clean Architecture (ports & adapters) for the backend

- Status: accepted
- Date: 2026-11-17

## Context

The case is small, but the parts most likely to change are exactly the framework-heavy ones:
the LLM provider, the agent framework (LangGraph), the vector store and the crawler. Reviewers
also judge architecture and code quality, and the core behaviour (validate a question, stream
an answer, only show sources that were actually cited) should be testable without network,
API keys or framework mocks.

## Decision

Four layers, with source-code dependencies pointing inward only:

| Layer | Contains | May import |
|---|---|---|
| `domain` | Entities and value objects (`Document`, `Chunk`, `SourceRef`, `SessionId`, `Question`), pure rules (URL normalisation, cited-source selection), domain errors | stdlib only |
| `application` | Ports (`typing.Protocol`), use cases, stream-event DTOs | `domain` |
| `infrastructure` | Adapters implementing ports: crawler, chunker, Chroma, hybrid retriever, LangGraph agent | `application`, `domain`, frameworks |
| `interface` | FastAPI (SSE) and Typer CLI | `application`, `domain`, web frameworks |

`container.py` is the composition root and the only place adapters are bound to ports.

The rule is **enforced, not just documented**: `import-linter` contracts in `pyproject.toml`
fail CI if `domain`/`application` import LangChain, LangGraph, OpenAI, FastAPI, Chroma, httpx
or pydantic, or if an inner layer imports an outer one.

Ports are `typing.Protocol`s (structural typing), so adapters and test fakes do not inherit
from anything and mypy still checks conformance at the wiring site.

## Consequences

- The LangGraph agent is one adapter behind `ChatAgentPort`. Replacing it (e.g. with a plain
  LangChain chain or another framework) touches `infrastructure/orchestration` and `container.py`
  only; use cases, API and tests of the core are unchanged.
- Use cases are unit-tested with in-memory fakes; framework code is covered by integration tests.
- Cost: some mapping code at the boundaries (LangChain messages → our own events, Chroma
  results → `ScoredChunk`). We accept it, as it keeps framework types out of the API contract.
- We deliberately do **not** add a repository/unit-of-work layer, a DI framework or
  per-use-case request/response objects: the case is too small for them to pay off.
