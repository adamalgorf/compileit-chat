# ADR-0007: Custom LangGraph orchestrator instead of a prebuilt agent; use case vs. orchestrator responsibilities

- Status: accepted (amends ADR-0002)
- Date: 2026-11-18

## Context

The case names **orchestration** as a requirement. Reviewers should be able to open one
folder and see how the agent decides what to do next: which steps exist, how it routes
between them, when it stops, and what it remembers.

The first version (ADR-0002) was already a custom graph, but it was compact: two nodes,
LangGraph's prebuilt `ToolNode` and `tools_condition`, and the recursion limit as the only
stop condition. Hitting that limit surfaced as an error. The mechanics worked, but the
orchestration was implicit, spread across framework defaults.

Separately, it must be clear where the business flow ends and the agent control flow
begins, so that replacing LangGraph never touches the application layer.

## Decision

### 1. A hand-built `StateGraph` in `infrastructure/orchestration/`, no prebuilt agent

```
START → call_model ──(tool calls)──────► run_tools → collect_sources → call_model
                   ├─(tool budget spent)─► handle_fallback → END
                   └─(final answer)──────► END
```

One responsibility per file:

| File | Holds |
|---|---|
| `state.py` | `AgentState`: `messages` (merged with `add_messages`), per-turn `sources` and `tool_iterations` |
| `routing.py` | `should_continue`, a pure function returning `tools`, `fallback` or `end` |
| `nodes.py` | `call_model`, `run_tools`, `collect_sources`, `handle_fallback` |
| `graph.py` | Wiring, `compile(checkpointer=…)`, and the derived recursion backstop |
| `tools.py` / `prompts.py` | Thin tool wrappers over ports; prompt text and the untrusted-content delimiting |
| `checkpointer.py` | The SQLite saver factory |
| `orchestrator.py` | `LangGraphOrchestrator`, which runs the graph and maps `astream_events` to application events |

Choices within that:

- **We don't use `create_react_agent` or `ToolNode`/`tools_condition`.** `run_tools` executes
  the calls itself (concurrently) and counts rounds. Routing is our own function, so the
  stop rule lives in our code and is unit-tested branch by branch.
- **The iteration budget is explicit state.** `tool_iterations` is reset every turn.
  `should_continue` sends a model that still wants tools after `AGENT_MAX_TOOL_ITERATIONS`
  rounds to `handle_fallback`.
- **A graceful stop instead of an exception.** `handle_fallback` first answers every open
  tool call with a "cancelled" tool message, because otherwise the next turn would send the
  model an invalid history. It then gives a polite Swedish fallback that points to the
  contact page. LangGraph's recursion limit stays as a hard backstop, derived from the
  graph's shape (`3 × rounds + 3`) rather than configured separately.
- **Sources are graph state.** `collect_sources` gathers the pages each tool round touched.
  The orchestrator emits them from that node's output, not by inspecting tool messages.
- **The diagram is generated** (`make docs`) into `docs/architecture.md`, and a test fails
  on drift.

### 2. The split between the use case and the orchestrator

| `AskQuestion` (application) | `LangGraphOrchestrator` (infrastructure) |
|---|---|
| Receives validated `SessionId`/`Question` value objects | Picks the thread (`thread_id` = session id) and loads memory |
| Calls `ChatAgentPort.stream` and passes events through | Runs the tool loop: routing, iteration budget, fallback |
| Decides which sources to show (only those the answer links to) | Reports every page the tools touched (`RetrievalEvent`) |
| Maps `AgentError` to one user-facing Swedish error | Translates provider errors, timeouts and the backstop into `AgentError` |
| Defines the client event contract (`… → Sources → Done` or `Error`) | Maps `astream_events` to `TokenEvent` / `ToolCallEvent` / `RetrievalEvent` |
| No LangGraph or LangChain imports (enforced by `import-linter`) | All LangGraph knowledge |

`container.py` is the only place that binds `LangGraphOrchestrator` to `ChatAgentPort`
(and `ConversationStorePort` for reset).

## Consequences

- The orchestration is readable without knowing LangGraph's prebuilt components, and every
  decision point has a test: routing branches, each node, and graph tests with a scripted
  model for tool call → answer, the fallback (including the turn after it), and follow-ups
  in the same thread.
- There is a little more code than with `ToolNode` (about 30 lines for `run_tools`) in
  exchange for an explicit iteration count and error policy: bad tool arguments are
  reported back to the model, while infrastructure failures fail the turn.
- `astream_events` produces more events than the two stream modes used before. We filter by
  node name, which couples the orchestrator to the node names defined in `graph.py`. They are
  constants in the same package, and the tests cover the mapping.
- Replacing LangGraph still touches only `infrastructure/orchestration/` and
  `container.py`, as ADR-0001 requires.

## Amendment (eval-driven): every turn starts with a site search

The first eval run (`docs/eval-report.md`) showed two behaviours that the prompt asked for but
the model delivered only intermittently:

- a follow-up answered from memory, without a tool call;
- "not found" concluded after reading one guessed page.

Both are now enforced in the graph instead of the prompt. `call_model` uses a model bound
with `tool_choice=search_website` when `tool_iterations == 0`, and the plain tool-bound
model afterwards. This keeps the use case unchanged and makes the invariant testable
(`test_first_step_of_a_turn_must_call_a_tool_later_steps_may_answer`).

Trade-offs, measured:

- About 0.3 s more median latency to the first token.
- Off-topic questions are searched once before the refusal. The search hits can tempt the
  model to answer, and in one run it wrote code; the scope rule at the top of the prompt
  covers this (24/24 refusals afterwards).
- Page requests ("sammanfatta Om oss") take one extra step: search, then `get_page`.

The general lesson from the eval is that **invariants go in the orchestrator, and judgement
goes in the prompt**.
