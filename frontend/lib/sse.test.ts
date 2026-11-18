import { describe, expect, it } from "vitest"

import { readSseEvents, toChatEvent, type RawSseEvent } from "@/lib/sse"

function streamOf(...chunks: (string | Uint8Array)[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(typeof chunk === "string" ? encoder.encode(chunk) : chunk)
      }
      controller.close()
    },
  })
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<RawSseEvent[]> {
  const events: RawSseEvent[] = []
  for await (const event of readSseEvents(stream)) events.push(event)
  return events
}

describe("readSseEvents", () => {
  it("parses named events", async () => {
    const events = await collect(
      streamOf('event: token\ndata: {"text": "Hej"}\n\nevent: done\ndata: {}\n\n'),
    )

    expect(events).toEqual([
      { event: "token", data: '{"text": "Hej"}' },
      { event: "done", data: "{}" },
    ])
  })

  it("reassembles events split across chunks", async () => {
    const events = await collect(streamOf("event: tok", 'en\ndata: {"te', 'xt": "a"}\n', "\n"))

    expect(events).toEqual([{ event: "token", data: '{"text": "a"}' }])
  })

  it("keeps multi-byte characters intact when a chunk splits them", async () => {
    const bytes = new TextEncoder().encode('event: token\ndata: {"text": "på"}\n\n')
    const splitAt = bytes.indexOf(0xc3) + 1 // in the middle of "å"

    const [event] = await collect(streamOf(bytes.slice(0, splitAt), bytes.slice(splitAt)))

    expect(event?.data).toBe('{"text": "på"}')
  })

  it("handles CRLF, comments, multi-line data and a final event without blank line", async () => {
    const events = await collect(
      streamOf(": keep-alive\r\n\r\nevent: x\r\ndata: line 1\r\ndata: line 2\r\n\r\ndata: last"),
    )

    expect(events).toEqual([
      { event: "x", data: "line 1\nline 2" },
      { event: "message", data: "last" },
    ])
  })
})

describe("toChatEvent", () => {
  it.each([
    [
      { event: "token", data: '{"text": "Hej"}' },
      { type: "token", text: "Hej" },
    ],
    [
      { event: "tool_start", data: '{"tool": "search_website", "query": "AI"}' },
      { type: "tool_start", tool: "search_website", query: "AI" },
    ],
    [
      { event: "tool_start", data: '{"tool": "list_pages", "query": null}' },
      { type: "tool_start", tool: "list_pages", query: null },
    ],
    [
      { event: "sources", data: '{"sources": [{"title": "Om oss", "url": "https://x/om"}]}' },
      { type: "sources", sources: [{ title: "Om oss", url: "https://x/om" }] },
    ],
    [{ event: "done", data: "{}" }, { type: "done" }],
    [
      { event: "error", data: '{"message": "Fel"}' },
      { type: "error", message: "Fel" },
    ],
  ])("maps %j", (raw, expected) => {
    expect(toChatEvent(raw)).toEqual(expected)
  })

  it.each([
    { event: "token", data: "not json" },
    { event: "token", data: '{"text": 1}' },
    { event: "sources", data: '{"sources": [{"title": "x"}]}' },
    { event: "unknown", data: "{}" },
    { event: "token", data: "[]" },
  ])("rejects malformed or unknown event %j", (raw) => {
    expect(toChatEvent(raw)).toBeNull()
  })
})
