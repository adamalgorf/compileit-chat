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

## Assumptions

Based on inspecting compileit.com (2026-11-17) before writing the crawler:

- **Swedish only.** Every page has `<html lang="sv">`, with no `/en` section or hreflang
  alternates. Language is still recorded per page, but no language filtering is needed.
- **Sitemap is complete and allowed.** `robots.txt` is `Allow: /` and points to
  `sitemap.xml` (96 URLs). The crawler is sitemap-first and only follows links if no sitemap
  is found. `www.compileit.com` 308-redirects to `compileit.com`, which is the canonical host.
- **Server-rendered HTML** (Next.js on Vercel), so no headless browser is needed.
- **Employee profile pages are excluded** (`/medarbetare/<id>-<name>`, ~45 URLs). They are
  thin, personal pages that add retrieval noise. Leadership and contact details are on
  `/kontakt`. Configurable via `CRAWL_EXCLUDE_PATTERNS`.
- **Custom main-content extraction instead of trafilatura.** On this site trafilatura keeps
  only one block of card-based pages (368 chars of `/tjanster/ai`) and drops the headings on
  `/kontakt`. The site has a clean `<main>`, which is rendered to markdown directly.
  trafilatura is the fallback for pages without `<main>`.
- **Job ads have almost no text** on the site itself (the content is loaded from an external
  service), so questions about open positions get thin answers.
- **The crawl snapshot is committed** (`backend/data/snapshot/pages.jsonl`) rather than
  crawling on first start. This makes the app and the eval reproducible without hitting the
  site, and `git diff` after `make ingest` shows exactly what changed on the site. The vector
  index is derived data: it is built from the snapshot (`make index`, ~1 cent of embeddings)
  and is not committed.

## Development

Requires [uv](https://docs.astral.sh/uv/) and `make`.

```bash
make install   # deps + pre-commit hooks
make check     # lint, architecture contracts, mypy, tests
```
