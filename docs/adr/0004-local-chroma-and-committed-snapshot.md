# ADR-0004: Local Chroma index, built from a committed crawl snapshot

- Status: accepted
- Date: 2026-11-17

## Context

We need a vector store and somewhere to keep full page texts (for "summarise the About
page"). Reviewers must be able to run the app with only an `OPENAI_API_KEY`: no cloud
accounts and no extra services.

## Decision

- **Chroma, persistent and embedded** (`chromadb.PersistentClient`), stored in git-ignored
  `backend/data/runtime/chroma`. No server process, no account, and it persists across
  restarts. Telemetry is disabled.
- **Embeddings are computed by us** through `EmbeddingPort` and handed to Chroma, rather
  than using Chroma's embedding functions. The store only stores and searches, so the
  embedding model is swappable in one place.
- **Full page texts live in a JSON-lines file** that is also the **committed crawl
  snapshot** (`backend/data/snapshot/pages.jsonl`): one page per line, sorted, UTF-8.
- **The index is derived data and is not committed.** It is rebuilt from the snapshot with
  `make index`, which costs about a cent of embeddings.
- `replace_all` builds a staging collection and then swaps it in, so a failed rebuild
  leaves the old index intact.

We chose committing the snapshot over crawling on first start because it makes runs
reproducible: the eval scores refer to known content, startup does not depend on the site
being up, and `git diff` after a re-crawl shows exactly what changed on compileit.com.

## Consequences

- The data can drift from the live site until someone runs `make ingest`. A scheduled
  re-crawl is listed as a next step.
- Chroma is fine at this scale (~100 chunks). A production deployment with many sites would
  move to a managed store (pgvector, a hosted vector DB) behind the same `VectorStorePort`.
