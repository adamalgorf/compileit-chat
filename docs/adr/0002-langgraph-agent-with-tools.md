# ADR-0002: A tool-calling LangGraph agent (custom graph) instead of a fixed RAG chain

- Status: accepted
- Date: 2026-11-18

## Context

The simplest design is a fixed chain: embed the question, retrieve top-k, stuff the
results into a prompt and answer. The case questions show where that falls short:

- *"Sammanfatta sidan 'Om oss' i tre punkter"* needs the **whole page**, not three chunks.
- *"Berätta mer om den andra punkten"* must be **rewritten** into a standalone query before
  retrieval can work.
- *"Vad kostar en Tesla?"* should be refused **without** retrieving anything.
- *"Hur kontaktar man er, och var sitter ni?"* is two questions and may need two lookups.

The case also requires an orchestration framework with tool calling.

## Decision

A tool-calling agent built as an explicit LangGraph `StateGraph`:

```
START → agent ─(tool calls?)→ tools → agent → … → END
```

- **Tools**: `search_website` (hybrid retrieval), `get_page` (a full page by URL, path or
  title) and `list_pages`. Arguments are Pydantic-typed, with Swedish descriptions. Each tool
  returns content for the model, wrapped in `<källa>` tags as untrusted data, plus an
  *artifact* listing the pages it touched. The adapter turns artifacts into
  `RetrievalEvent`s, and `AskQuestion` keeps only the pages the answer actually links to.
- **Why a custom graph instead of `create_react_agent`**: the loop is the same, but three
  things we care about are explicit in about 40 lines:
  - the system prompt is injected on every model call and never stored in the checkpoint,
    so prompt changes apply to old sessions too;
  - earlier turns are trimmed before the model sees them (`bounded_history`), cut at a user
    message so a tool result is never separated from its call;
  - the loop is bounded by LangGraph's recursion limit (`AGENT_MAX_STEPS`).

  The prebuilt agent has hooks for all of this, but each hook adds indirection that a
  reviewer has to look up.
- **Behaviour lives in the prompt** (`infrastructure/agent/prompts.py`): answer only from
  this turn's tool results, use a fixed "Det hittar jag inte på compileit.com." phrase,
  refuse off-topic questions without searching, keep answers short, and cite sources as
  markdown links.
- **Model**: `gpt-4.1-mini` at temperature 0.1, configurable via `CHAT_MODEL`.

### Swappability

The agent is one adapter (`LangGraphChatAgent`) behind `ChatAgentPort` and
`ConversationStorePort`. It translates LangGraph's stream into our own events (`TokenEvent`,
`ToolCallEvent`, `RetrievalEvent`) and every failure into `AgentError`. Replacing LangGraph
with a plain LangChain chain, another framework or a hand-written loop touches
`infrastructure/agent/` and `container.py` only. The use cases, the API, the SSE contract
and their tests stay as they are, and `import-linter` enforces that boundary in CI.

## Evidence from the first live run

The first prompt version answered *"Berätta mer om den andra punkten"* from conversation
memory without a tool call, so the answer had no source card. It also built the industry
list partly from a general article about app ratings. Two prompt rules fixed both:

- every turn, including follow-ups, must call a tool;
- industry lists may be built only from Compileit's own case studies.

On the next run the follow-up fetched `/om-oss` itself and the industries came from
`/uppdrag`.

## Consequences

- Answers cost 2-3 model calls (decide → tool → answer) instead of 1. With
  `gpt-4.1-mini` the first token still arrives in about 1-3 s.
- Prompt behaviour is probabilistic, so it is measured by the eval suite (`make eval`),
  not by unit tests. Unit and integration tests drive the real graph with a scripted chat
  model to pin down the mechanics: streaming, memory, reset, the step limit and errors.
