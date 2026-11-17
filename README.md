# Compileit chat

A chat that answers questions **in Swedish** about the content of
[compileit.com](https://www.compileit.com), streams its answers, cites its sources and says
clearly when something is not on the site.

> Work in progress — built in phases, see `git log`. This README is completed in the final phase.

## Repository layout

```
backend/    Python 3.12 · FastAPI · LangChain + LangGraph · OpenAI (Clean Architecture)
frontend/   Next.js (App Router) · TypeScript · Tailwind
docs/adr/   Architecture Decision Records
ai-history/ Exported AI session transcripts
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and `make`.

```bash
make install   # deps + pre-commit hooks
make check     # lint, architecture contracts, mypy, tests
```
