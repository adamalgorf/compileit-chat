# Prompt-design session: from case PDF to build prompt (Claude chat)

Exported from the Claude chat (claude.ai) session that came **before** the build session in
`01-build-session.md`. Here the case PDF was read, an approach was proposed, and the build
prompt that was later handed to Claude Code was written and then corrected.
User and assistant messages are verbatim; tool calls are summarised. The assistant's private
reasoning is not included. The final version of the generated prompt is in the appendix.

---

## User (1)

@"2026-caseuppgift-ai-engineer.pdf"

🔧 Read the PDF (3 pages) with `pdftotext`.

## Assistant (1)

Jag har läst caset från Compileit. Det här ska byggas:

**Uppgiften:** en chatt på svenska som svarar på frågor om innehållet på compileit.com, byggd som en RAG-lösning.

**Krav som går att pricka av:**
- Svaren streamas till UI:t och är korta och korrekta.
- Finns svaret inte i källan ska chatten säga det rakt ut.
- Den ska klara uppföljningsfrågor inom samma session.
- Chattvyn ska vara responsiv för både mobil och desktop.
- Agenten ska bygga på ett orchestration-ramverk med tool calling.

**Rekommenderad stack (valfri):** Python, OpenAI, LangChain/LangGraph och Next.js.

**Det du ska leverera:**
- Ett GitHub-repo där användaren `Compileit-case` bjuds in, plus ett mail när du är klar.
- En `/ai-history`-mapp med dina AI-sessioner. Den här konversationen räknas, så exportera den.
- En README med körinstruktioner, en sektion "Why this design" (2–5 punkter), dina antaganden och testfrågorna.

**Så här skulle jag lägga upp det:**
1. **Indexering:** ett crawl-skript som läser sitemap.xml, hämtar sidorna, rensar bort meny och sidfot och delar texten i chunkar. Varje chunk får URL och sidtitel som metadata. Embeddings görs med OpenAI och lagras i Chroma eller FAISS lokalt.
2. **Agent:** en LangGraph-agent med ett `search_website`-verktyg. Konversationen sparas per session med en checkpointer som nycklas på `thread_id`. Systemprompten säger att agenten bara får svara utifrån verktygsresultaten, ska citera käll-URL:er och annars säga "det framgår inte av webbplatsen".
3. **API:** FastAPI med en streaming-endpoint (SSE) som skickar både tokens och källor.
4. **Frontend:** Next.js med en enkel chattvy, klickbara källor under svaren, laddningsindikator och knappen "Ny konversation".
5. **Kvalitet:** Docker Compose för att starta allt med ett kommando, och några enkla tester på retrieval och på att agenten vägrar svara när källan saknas.

Ska jag börja bygga? Säg i så fall om du vill följa den rekommenderade stacken ovan eller byta något.

---

## User (2)

Den filen och ge mig en prompt som jag kan ge Claude så att den kan bygga applikationen. Jag vill att du tar hänsyn till att detta är ett case och jag vill imponera. Jag vill också att det ska vara enligt clean architecture-principer. Det ska vara LangChain, LangGraph. Kör.

🔧 Wrote `compileit-case-prompt.md` (first version) and sent it as a file.

## Assistant (2)

I've written the prompt in compileit-case-prompt.md. Paste everything below the line into Claude Code, in an empty folder that's already a git repo. It's in English because Claude Code works more precisely that way and the reviewers will read it in `/ai-history`. The UI and the answers will still be in Swedish.

**What makes it stand out:**
- **Clean architecture is enforced, not just named.** The prompt spells out exactly which layers may import which frameworks. LangGraph sits behind its own interface and everything is wired together in one place.
- **The agent has three tools** for searching the site, reading a whole page and listing pages. It also remembers each session across restarts and treats text from the website as untrusted data.
- **There's an eval suite with a report.** It runs the case's test questions plus questions that should be refused and measures how well the answers match the sources.
- **The chat shows what the agent is doing**, for example "Söker på webbplatsen…", and lists clickable sources under each answer.
- **The git history is built in phases with clear commits.**

**Tips:**
- Keep the prompt's instruction that Claude plans before each phase.
- Export the Claude Code session and this chat to `/ai-history` when you're done.
- Read the architecture decision notes in `docs/adr/` before the interview.

---

## User (3)

why is there no orchestrator file?

🔧 Edited `compileit-case-prompt.md`: renamed `infrastructure/agent/` to `infrastructure/orchestration/`, added an explicit custom `StateGraph` file layout and graph shape, the use case vs. orchestrator split, an ADR, and routing/graph tests in phase 4. Re-sent the file.

## Assistant (3)

Bra fångat, det var en lucka i prompten. Orkestreringen fanns bara gömd i en mapp som hette `agent/` och skulle hållas ihop av "graph, tools, prompts". Dessutom lät jag Claude välja `create_react_agent`, som är en färdig svart låda. Orkestrering är ett uttalat krav i caset, så granskarna kommer att leta efter den först. Den måste synas direkt och vara byggd för hand.

Jag har uppdaterat compileit-case-prompt.md:

- **Mappen heter nu `infrastructure/orchestration/`** och har en tydlig fil per ansvar: `state.py`, `graph.py`, `nodes.py`, `routing.py`, `tools.py`, `prompts.py`, `checkpointer.py` och `orchestrator.py`.
- **Grafen byggs som en egen `StateGraph`.** Modellen anropas, verktyg körs, källor samlas in och det finns en reservväg när agenten når max antal varv.
- **Diagrammet genereras från koden** med `draw_mermaid()`.
- **Ansvaret är uttryckligen uppdelat.** Use caset styr affärsflödet utan att känna till LangGraph, och orkestratorn styr agentens flöde.
- **Fas 4 innehåller nu tester** av routingen och av hela grafen med en fejkad LLM.

---

## User (4)

ge mig en korrektions prompt för jag har redan matat in förra filen

## Assistant (4)

Klistra in det här i samma Claude Code-session. Prompten fungerar oavsett hur långt bygget har kommit:

> The correction prompt below is the one pasted into the build session (see "Spec correction" in `01-build-session.md`).

```
Correction to the original spec – please apply before continuing.

The agent orchestration is not explicit enough. "Orchestration" is a named requirement in the case and reviewers will look for it first, so it must be easy to find and hand-built. Changes:

1. Rename `infrastructure/agent/` → `infrastructure/orchestration/`.

2. Do NOT use `create_react_agent` or any other prebuilt agent. Build a custom LangGraph `StateGraph` with this file layout:

   orchestration/
     state.py          # AgentState (TypedDict): messages (add_messages reducer), sources, tool_iterations
     graph.py          # build_graph(): nodes, edges, conditional routing, compile(checkpointer=...)
     nodes.py          # call_model, run_tools, collect_sources, handle_fallback
     routing.py        # should_continue: → tools / fallback / end
     tools.py          # search_website, get_page, list_pages (thin wrappers calling ports)
     prompts.py        # system prompt + untrusted-context delimiting
     checkpointer.py   # AsyncSqliteSaver factory
     orchestrator.py   # LangGraphOrchestrator – implements ChatAgentPort, runs the compiled
                       # graph, maps astream_events → application StreamEvent DTOs

3. Graph shape:
   START → call_model ──(tool calls)──► run_tools → collect_sources → call_model
                      ├─(max iterations)──► handle_fallback → END
                      └─(final answer)───► END

4. Separation of concerns: `application/use_cases/ask_question.py` handles the business flow (validate input, call ChatAgentPort, yield events) with zero LangGraph imports. The orchestrator owns agent control flow. `container.py` wires LangGraphOrchestrator to ChatAgentPort.

5. Generate the graph diagram from code (`graph.get_graph().draw_mermaid()`) into `docs/architecture.md`, so docs never drift from the implementation.

6. Add an ADR: "Custom LangGraph orchestrator vs. prebuilt agent, and use case vs. orchestrator responsibilities".

7. Tests: unit tests for `routing.py` (each branch) and a graph test with a fake LLM covering tool-call → answer, max-iteration fallback, and a follow-up question within the same thread_id.

How to proceed:
- If the agent is not built yet: just follow this structure when you get there.
- If it's already built: refactor it in its own commit (`refactor: extract explicit LangGraph orchestrator`). Keep behaviour identical, make sure lint/mypy/tests pass, then continue with the plan.

First give me a short summary of what you'll change, then do it.
```

Om orkestreringen redan är byggd hamnar omstruktureringen i en egen commit. Det ser bra ut i git-historiken, eftersom det visar att du förbättrade designen medvetet längs vägen.

---

## User (5)

ladda upp denna konversation till github repot

🔧 Cloned the repo and added this transcript as `ai-history/00-prompt-design-session.md`.

---

## Appendix: final build prompt (`compileit-case-prompt.md`, after the orchestrator correction)

````markdown
# Build prompt – Compileit AI Engineer case

> Paste everything below this line into Claude Code (in an empty folder that is a git repo).

---

You are a senior AI engineer helping me build a **take-home case for an AI Engineer role at Compileit**. The goal is not just a working app: the reviewers explicitly judge **architecture, design/UX and code quality**, and they will read the git history and my AI session logs in a technical interview. Build something a senior engineer would be proud to defend — clean, deliberate, well-tested, no over-engineering for its own sake.

## 1. The case (requirements from Compileit)

Build a chat that answers questions **in Swedish** about the content of the public website **https://www.compileit.com**.

Hard requirements:
- **Generation:** answers are correct, concise, and **streamed** to the UI.
- **Hallucination:** if the answer is not in the source, the chat must **clearly say so**.
- **Context:** follow-up questions within the same session must work.
- **UX:** simple, responsive chat view that works on mobile and desktop.
- **Orchestration:** use an orchestration framework as the foundation of the agent **with tool calling**.

Stack (mandatory for me): **Python backend, LangChain + LangGraph, OpenAI, Next.js frontend.**

Deliverables:
- GitHub repo with meaningful, incremental history.
- `/ai-history` folder (I will put exported AI transcripts there — create the folder with a short README explaining it).
- `README.md` with: how to run, **"Why this design"** (2–5 bullets), assumptions, example test questions, limitations/next steps.

The app must handle these test questions well:
1. "Vad erbjuder ni för typer av AI-tjänster?"
2. "Vilka branscher jobbar ni med?"
3. "Hur kontaktar man er, och var sitter ni?"
4. "Har ni beskrivit hur ni jobbar med säkerhet/sekretess?"
5. "Sammanfatta sidan 'Om oss' i tre punkter och länka källan."
Plus a follow-up (e.g. "Berätta mer om den andra punkten") and an out-of-scope question (e.g. "Vad kostar en Tesla?") that must be politely refused.

## 2. Architecture – Clean Architecture (non-negotiable)

Use Clean Architecture / ports & adapters in the backend. **Dependency rule: source code dependencies point inward only.** Domain and application layers must not import LangChain, LangGraph, OpenAI, FastAPI, Chroma or any other framework.

```
backend/
  src/compileit_chat/
    domain/            # Pure Python. Entities & value objects, domain errors.
                       #   Document, Chunk, SourceRef, ChatMessage, Answer, SessionId …
    application/
      ports/           # Abstract interfaces (typing.Protocol / ABC):
                       #   EmbeddingPort, VectorStorePort, RetrieverPort, WebCrawlerPort,
                       #   ContentExtractorPort, ChatAgentPort, ConversationStorePort
      use_cases/       # IngestWebsite, AskQuestion (streams events), ResetConversation
      dto.py           # Stream event types: Token, ToolCall, Sources, Done, Error
    infrastructure/    # Adapters implementing ports – frameworks live ONLY here
      crawling/        # sitemap-first crawler (httpx), robots.txt respected, trafilatura extraction
      chunking/        # heading-aware chunker
      vectorstore/     # Chroma (persistent, local) adapter
      retrieval/       # hybrid retriever (vector + BM25) with reciprocal rank fusion
      llm/             # OpenAI chat/embedding factories (LangChain)
      orchestration/   # THE agent orchestrator (LangGraph) – see §4 for the file layout
    interface/
      api/             # FastAPI: routers, SSE streaming, request/response schemas, error handlers
      cli/             # `ingest` command (Typer)
    config.py          # pydantic-settings, all models/params via env
    container.py       # Composition root – the ONLY place adapters are wired to ports
  tests/
    unit/              # domain + use cases with fake adapters (no network)
    integration/       # adapters, API with mocked LLM
    eval/              # golden-question eval (see §6)
frontend/              # Next.js
docs/adr/              # Architecture Decision Records
ai-history/
```

Rules:
- Dependency injection through `container.py`; use cases receive ports in their constructor.
- The LangGraph agent is an adapter behind `ChatAgentPort`. Swapping LangGraph for something else must not touch the application layer — mention this in an ADR.
- Typed everywhere (mypy strict on `domain` and `application`), small functions, no god files, no dead code, docstrings where intent is not obvious.
- Tooling: `uv`, `ruff` (lint + format), `mypy`, `pytest`, `pre-commit`. Frontend: TypeScript strict, ESLint, Prettier.

## 3. Ingestion pipeline

1. **Before writing the crawler, actually inspect compileit.com** (sitemap.xml, robots.txt, page structure, language versions) and adapt to what you find. Document findings as assumptions in the README.
2. Sitemap-first discovery, fallback to same-domain link crawl with depth/page limits. Prefer Swedish pages; record language in metadata.
3. Extract main content (strip nav/footer/cookie banners), normalize whitespace, dedupe by content hash.
4. Heading-aware chunking (~500–800 tokens, small overlap). Each chunk carries metadata: `url`, `title`, `section_heading`, `lang`, `crawled_at`.
5. Also store **full page text** keyed by URL so the agent can read a whole page (needed for "summarize the About page").
6. CLI: `make ingest` (idempotent, re-runnable, logs a summary: pages, chunks, skipped).
7. Commit a small snapshot of the crawled data **or** make ingestion run automatically on first start — choose and justify.

## 4. Agent (LangGraph) – the core

Build an **explicit, custom LangGraph `StateGraph` orchestrator** – no `create_react_agent` black box. The orchestration must be easy to find and read, because "Orchestration" is a named requirement and reviewers will look for it first.

File layout (`infrastructure/orchestration/`):
```
orchestration/
  state.py          # AgentState (TypedDict): messages (add_messages reducer), sources, tool_iterations
  graph.py          # build_graph(): nodes, edges, conditional routing, compile(checkpointer=...)
  nodes.py          # node functions: call_model, run_tools, collect_sources, handle_fallback
  routing.py        # conditional edge logic: should_continue (tools / fallback / end)
  tools.py          # search_website, get_page, list_pages (thin wrappers calling ports)
  prompts.py        # system prompt + context-formatting (untrusted-data delimiting)
  checkpointer.py   # AsyncSqliteSaver factory
  orchestrator.py   # LangGraphOrchestrator – implements ChatAgentPort; runs the compiled graph
                    # and maps astream_events to the application's StreamEvent DTOs
```

Graph shape (also draw it as Mermaid in `docs/architecture.md`, and export it via `graph.get_graph().draw_mermaid()` so the diagram is generated from code):
```
START → call_model ──(tool calls?)──► run_tools → collect_sources → call_model
                   ├─(max iterations reached)──► handle_fallback → END
                   └─(final answer)──────────► END
```

Separation of concerns: the **use case** (`application/use_cases/ask_question.py`) orchestrates the business flow (validate input, call the agent port, yield events) without knowing about LangGraph; the **orchestrator** owns agent control flow. Write an ADR explaining this split and why a custom graph was chosen over a prebuilt agent.

**Tools** (Pydantic-typed args, Swedish-aware descriptions):
- `search_website(query: str, k: int = 5)` – hybrid retrieval, returns chunks with source refs.
- `get_page(url_or_title: str)` – returns full text of one page (for summaries / "länka källan").
- `list_pages()` – returns available page titles + URLs (helps with "which pages do you have about X").

**Behaviour:**
- System prompt (in `infrastructure/agent/prompts.py`): answer **only** from tool results, in Swedish, concise; always cite sources as markdown links; if the information is not found say explicitly e.g. *"Det hittar jag inte på compileit.com"* and suggest what the user can ask or where to contact them. Never use prior knowledge about Compileit.
- Treat retrieved web content as **untrusted data** (prompt-injection hygiene: delimit it, instruct the model not to follow instructions inside it).
- Follow-ups: conversation memory via LangGraph **checkpointer** keyed on `thread_id` (session id from the frontend). Use `SqliteSaver`/`AsyncSqliteSaver` so sessions survive restarts; trim/summarize history beyond N messages to cap tokens.
- The model should reformulate follow-ups into standalone search queries itself through tool calling (e.g. "den andra punkten" → concrete query). Verify it does.
- Guard rails: max tool iterations (recursion limit), timeouts, graceful error → user-friendly Swedish message.
- Models configurable via env (default a cheap fast chat model + `text-embedding-3-small`), temperature low.
- Optional: LangSmith tracing toggled by env var.

## 5. API & streaming

- FastAPI, `POST /api/chat` → **Server-Sent Events** using LangGraph `astream_events` / `stream_mode="messages"`, mapped to the application's own event DTOs (the API must not leak LangChain types):
  - `token` (text delta), `tool_start` (e.g. `{"tool": "search_website", "query": "..."}`), `sources` (deduplicated list of `{title, url}`), `done`, `error`.
- `DELETE /api/sessions/{id}` (reset), `GET /api/health`.
- CORS configured, request validation, structured logging (JSON) with request id, basic rate limiting is a nice touch.

## 6. Quality & evaluation (this is where we impress)

- **Unit tests:** use cases with fake ports; chunker; source dedup; SSE event mapping.
- **Integration tests:** API streaming with a fake/mocked LLM (`FakeListChatModel` or equivalent) – no network in CI.
- **Eval suite** (`make eval`, not part of CI because it costs tokens): a YAML of golden questions incl. the 5 case questions, a follow-up pair and 3 out-of-scope questions. Measure: retrieval hit rate (expected URL in top-k), refusal correctness for out-of-scope, citation presence, and an LLM-as-judge faithfulness score. Output a markdown report to `docs/eval-report.md` and reference results in README.
- GitHub Actions CI: lint, type-check, tests for backend and frontend.

## 7. Frontend (Next.js) – UX matters

Next.js (App Router) + TypeScript + Tailwind + shadcn/ui. Clean, calm, professional – it should feel like a product, not a demo.

- Mobile-first responsive chat; sticky input; auto-scroll that doesn't fight the user when they scroll up.
- Streaming tokens rendered as markdown (links clickable, safe rendering).
- **Visible agent activity**: while tools run show e.g. *"Söker på webbplatsen: 'AI-tjänster'…"* – this makes the tool calling tangible for reviewers.
- **Source cards** under each answer (title + domain, open in new tab).
- Empty state with the example questions as clickable suggestion chips.
- "Ny konversation" button (new session id, calls reset), stop-generation button, copy answer, retry on error.
- Session id persisted in `localStorage` so a reload keeps the conversation.
- Accessibility: keyboard navigation, focus states, aria-live for streaming area, sufficient contrast; dark mode.
- All UI copy in Swedish.
- Keep frontend clean too: `components/`, `hooks/useChatStream.ts` (SSE parsing isolated), `lib/api.ts`, typed event union mirroring backend DTOs.

## 8. DevEx & delivery

- `docker-compose.yml` running backend + frontend; `make dev`, `make ingest`, `make test`, `make eval`, `make lint`.
- `.env.example` (never commit secrets). Only `OPENAI_API_KEY` required to run.
- `docs/adr/`: 4–6 short ADRs (Clean Architecture, LangGraph agent with tools vs. fixed RAG chain, hybrid retrieval, Chroma local store, SSE vs WebSockets, SQLite checkpointer for sessions).
- `docs/architecture.md` with a Mermaid diagram of layers + request flow.
- README (English, concise, scannable): overview + screenshot/GIF placeholder, quick start (≤ 3 commands), architecture summary, **Why this design (2–5 bullets)**, assumptions, example questions incl. expected behaviour, eval results, limitations & what I'd do next (e.g. scheduled re-crawl, reranker, auth, observability in prod).

## 9. How to work

- Work in **phases**, and **commit after each meaningful step** with Conventional Commits (`feat:`, `test:`, `refactor:`, `docs:` …) so the history tells the story:
  1. Scaffold repo, tooling, CI skeleton, domain + ports
  2. Crawler + ingestion + tests
  3. Retrieval + tests
  4. LangGraph orchestrator (state, graph, nodes, routing, tools, checkpointer) + unit tests of routing and graph with a fake LLM
  5. FastAPI SSE + integration tests
  6. Frontend
  7. Eval suite + tuning based on results
  8. Docs, ADRs, README polish
- Before each phase, give me a short plan; after each phase, run lint/type-check/tests and report.
- When you make an assumption, write it down (README "Assumptions").
- Prefer simple, readable solutions over clever ones. Do not add features outside this spec without asking.
- At the end, run the 5 case questions + follow-up + out-of-scope question end-to-end and show me the answers, then do a self-review against the evaluation criteria (architecture, UX, code quality) and fix what's weak.

Start with phase 1.

````
