# ADR-0005: Stream answers with Server-Sent Events (not WebSockets)

- Status: accepted
- Date: 2026-11-18

## Context

Answers must stream to the UI token by token, together with agent activity ("Söker på
webbplatsen…") and the cited sources. The traffic is one request (a question) followed by a
one-way stream of events (the answer).

## Decision

`POST /api/chat` returns `text/event-stream`. Each application event becomes one named SSE
event with a JSON payload: `token`, `tool_start`, `sources`, `done` or `error`. The contract
is documented in `interface/api/sse.py` and mirrored as a TypeScript union in the frontend.

- **Validation happens before the stream starts**, so a bad request gets an ordinary 422
  JSON response instead of a half-open stream.
- **Errors after the stream has started** (the headers are already sent) end it with a
  single `error` event carrying a Swedish message. A stream ends with either `done` or
  `error`, never both and never neither.
- **Stop generation** is the client aborting the request. Starlette cancels the response
  generator, which cancels the LangGraph run.
- `Cache-Control: no-cache` and `X-Accel-Buffering: no` keep proxies from buffering tokens.
- The frontend reads the stream with `fetch` + `ReadableStream` rather than `EventSource`,
  because `EventSource` cannot send a POST body.

## Alternatives considered

- **WebSockets**: full duplex, which we do not need. It also adds connection state,
  reconnect logic and a second protocol to secure and test, and it works less well with
  proxies, CORS and plain HTTP tooling (`curl -N` shows an SSE stream as-is).
- **Plain chunked text**: simpler, but it cannot carry typed events (tool activity, sources)
  without inventing our own framing. SSE is that framing, already standardised.

## Consequences

- Each question is a plain, stateless HTTP request. Rate limiting, logging, CORS and tests
  (`TestClient` reads the stream as text) work unchanged.
- No automatic resume: if a connection drops mid-answer, the UI offers "Försök igen".
  Resumable streams would need event ids and server-side buffering, which this case does
  not justify.
