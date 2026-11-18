# Architecture Decision Records

Short records of the decisions that shape this codebase: the context, the decision, and the
consequences we accepted. Where a later finding changed a decision, the ADR is amended in
place with a note rather than rewritten, so the reasoning history stays visible.

| ADR | Decision |
|---|---|
| [0001](0001-clean-architecture.md) | Clean Architecture (ports & adapters), with the dependency rule enforced by `import-linter` in CI |
| [0002](0002-langgraph-agent-with-tools.md) | A tool-calling LangGraph agent instead of a fixed RAG chain (amended by 0007) |
| [0003](0003-hybrid-retrieval.md) | Hybrid retrieval (vector + BM25, RRF). BM25 contributes its top 3 only, based on measurements |
| [0004](0004-local-chroma-and-committed-snapshot.md) | Local Chroma index built from a committed crawl snapshot |
| [0005](0005-sse-over-websockets.md) | Server-Sent Events for streaming, not WebSockets |
| [0006](0006-sqlite-checkpointer-for-sessions.md) | Conversation memory in LangGraph's SQLite checkpointer |
| [0007](0007-custom-orchestrator-and-responsibilities.md) | Hand-built orchestrator instead of a prebuilt agent; use case vs. orchestrator responsibilities; every turn starts with a site search (eval-driven) |
| [0008](0008-accounts-history-and-secrets.md) | User accounts (Argon2id, server-side sessions), saved chat history, login and API call logs, and the OpenAI key encrypted in the database (SQLAlchemy + Alembic, SQLite by default) |
