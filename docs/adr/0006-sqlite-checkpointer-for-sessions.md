# ADR-0006: Conversation memory in LangGraph's SQLite checkpointer

- Status: accepted
- Date: 2026-11-18

## Context

Follow-up questions need the earlier turns of the same session, and the brief asks for
sessions that survive restarts. The frontend generates a session id and keeps it in
`localStorage`.

## Decision

- The session id is the LangGraph **`thread_id`**. Every turn's messages, including tool
  calls and tool results, are stored by `AsyncSqliteSaver` in git-ignored
  `backend/data/runtime/checkpoints.sqlite3`.
- `Container.chat()` opens the saver as an async context manager. The API keeps it open for
  the app's lifetime (FastAPI lifespan), so there is one connection per process.
- **Reset** (`DELETE /api/sessions/{id}`) calls `adelete_thread`.
- **Bounded cost**: the checkpoint keeps the full history, but the model sees only the
  current turn plus up to `HISTORY_MAX_MESSAGES` (20) earlier messages, cut at a user
  message. We trim rather than summarise: with short answers and a 20-message window,
  summarisation would add a model call per turn for little gain.

## Alternatives considered

- **In-memory saver**: simplest, but sessions vanish on restart. It is used in tests.
- **Our own message table**: possible, but it would duplicate what the checkpointer already
  does, and it would lose tool-call/tool-result pairs unless we modelled them ourselves.
- **Postgres/Redis savers**: the right choice for several API replicas. They use the same
  interface, so switching means changing the one `AsyncSqliteSaver` line in `container.py`.

## Consequences

- SQLite allows one writer at a time, which is fine for a single API process and not for
  horizontal scaling (see above).
- Stored sessions grow without bound. A production version would expire threads after N
  days. This is listed under next steps.
