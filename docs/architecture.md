# Architecture

The backend uses Clean Architecture: framework-free `domain` and `application` layers, with
adapters around them. A hand-built LangGraph orchestrator is one of those adapters. The
frontend talks to it over Server-Sent Events. Rationale: [ADRs](adr/).

## Layers

Source-code dependencies point inward only. `import-linter` enforces this in CI
(`backend/pyproject.toml`).

```mermaid
flowchart TB
    subgraph interface["interface (FastAPI · Typer)"]
        api["api/: routes, SSE encoding, rate limit, JSON logs"]
        cli["cli/: ingest, docs"]
    end
    container["container.py: composition root"]
    subgraph infrastructure["infrastructure (frameworks live here)"]
        orchestration["orchestration/: LangGraph StateGraph"]
        retrieval["retrieval/: vector + BM25, RRF"]
        stores["vectorstore/ (Chroma) · storage/ (JSONL)"]
        crawling["crawling/ · chunking/ · llm/"]
    end
    subgraph application["application (no frameworks)"]
        usecases["use_cases/: AskQuestion, ResetConversation, IngestWebsite, BuildIndex"]
        ports["ports/: ChatAgentPort, RetrieverPort, …"]
    end
    domain["domain: Document, Chunk, SourceRef, SessionId, Question, citation rules"]

    interface --> container --> infrastructure
    interface --> application
    infrastructure -- implements --> ports
    application --> domain
    infrastructure --> domain
```

## Answering a question

```mermaid
sequenceDiagram
    autonumber
    participant UI as Next.js (useChatStream)
    participant API as FastAPI /api/chat
    participant UC as AskQuestion (use case)
    participant O as LangGraphOrchestrator
    participant G as StateGraph
    participant T as Tools → RetrieverPort / DocumentStorePort

    UI->>API: POST {session_id, message}
    API->>API: validate (SessionId, Question), rate limit
    API->>UC: execute(session, question)
    UC->>O: stream(session, question)
    O->>G: astream_events(new turn, thread_id = session)
    G->>G: call_model → tool calls?
    G->>T: run_tools (search_website / get_page / list_pages)
    T-->>G: <källa>…</källa> + page artifacts
    G->>G: collect_sources → call_model → final answer
    G-->>O: on_tool_start, on_chat_model_stream, collect_sources output
    O-->>UC: ToolCallEvent, TokenEvent…, RetrievalEvent
    UC-->>API: ToolCall / Token…, then Sources (only cited pages), Done
    API-->>UI: SSE: tool_start, token…, sources, done
```

## Orchestration graph

Generated from `infrastructure/orchestration/graph.py` with `make docs`. A test fails if
this diagram and the code disagree.

<!-- generated:orchestration-graph:start -->
```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	call_model(call_model)
	run_tools(run_tools)
	collect_sources(collect_sources)
	handle_fallback(handle_fallback)
	__end__([<p>__end__</p>]):::last
	__start__ --> call_model;
	call_model -. &nbsp;end&nbsp; .-> __end__;
	call_model -. &nbsp;fallback&nbsp; .-> handle_fallback;
	call_model -. &nbsp;tools&nbsp; .-> run_tools;
	collect_sources --> call_model;
	run_tools --> collect_sources;
	handle_fallback --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```
<!-- generated:orchestration-graph:end -->

| Node | Responsibility |
|---|---|
| `call_model` | Adds the system prompt to the current turn plus up to 20 earlier messages (trimmed at a user message) and asks the model for tool calls or the final answer. |
| `run_tools` | Executes every tool call of the last model message concurrently, reports bad arguments back to the model, and increments `tool_iterations`. |
| `collect_sources` | Adds the pages that the latest tool round returned to the turn's `sources`, de-duplicated. |
| `handle_fallback` | Reached when the model still wants tools after `AGENT_MAX_TOOL_ITERATIONS` rounds. Closes the open tool calls and answers with a polite Swedish fallback. |
| `should_continue` | Pure routing after `call_model`: `tools`, `fallback` or `end`. |

`AgentState` holds `messages` (merged with `add_messages`) and two per-turn fields that are
reset on every question: `sources` and `tool_iterations`. The SQLite checkpointer persists
the state per `thread_id`, which is the session id.

### Who decides what

| Concern | Owner |
|---|---|
| Input validation, error-to-message mapping, which sources to show (only cited ones), the event contract for clients | `AskQuestion`, the use case. It has no LangGraph imports. |
| Tool loop, routing, iteration budget, fallback, memory, step backstop, timeout, mapping framework events to application events | `LangGraphOrchestrator` and the graph |
| Wiring `LangGraphOrchestrator` to `ChatAgentPort` / `ConversationStorePort` | `container.py` |

## Ingestion

```mermaid
flowchart LR
    sitemap["robots.txt + sitemap.xml"] --> crawler["SitemapCrawler"]
    crawler --> extractor["MainContentExtractor (&lt;main&gt; → markdown)"]
    extractor --> dedupe["IngestWebsite: drop empty and duplicate pages"]
    dedupe --> snapshot[("pages.jsonl (committed)")]
    snapshot --> chunker["HeadingAwareChunker"]
    chunker --> embed["OpenAI embeddings"]
    embed --> chroma[("Chroma (runtime)")]
    chroma --> bm25["BM25, built lazily at first search"]
```
