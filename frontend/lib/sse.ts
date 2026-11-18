import type { ChatStreamEvent, SourceLink } from "@/lib/types"

/** A raw Server-Sent Event, before it is interpreted. */
export type RawSseEvent = { event: string; data: string }

/**
 * Parse a byte stream as Server-Sent Events.
 *
 * `EventSource` cannot POST a body, so the chat request is a `fetch` and its body is parsed
 * here. Handles events split across chunks, multi-line `data:` fields, CRLF line endings and
 * `:` comment lines, per the SSE spec.
 */
export async function* readSseEvents(
  stream: ReadableStream<Uint8Array>,
): AsyncGenerator<RawSseEvent> {
  const reader = stream.getReader()
  const decoder = new TextDecoder() // `stream: true` keeps multi-byte chars split across chunks
  let buffer = ""
  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() ?? "" // the last block may be incomplete
      for (const block of blocks) {
        const event = parseBlock(block)
        if (event) yield event
      }
    }
    const last = parseBlock(buffer)
    if (last) yield last
  } finally {
    reader.releaseLock()
  }
}

function parseBlock(block: string): RawSseEvent | null {
  let event = "message"
  const data: string[] = []
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue
    const colon = line.indexOf(":")
    const field = colon === -1 ? line : line.slice(0, colon)
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "")
    if (field === "event") event = value
    else if (field === "data") data.push(value)
  }
  return data.length ? { event, data: data.join("\n") } : null
}

/** Interpret a raw event against the contract. Unknown or malformed events return `null`. */
export function toChatEvent(raw: RawSseEvent): ChatStreamEvent | null {
  let payload: unknown
  try {
    payload = JSON.parse(raw.data)
  } catch {
    return null
  }
  if (!isRecord(payload)) return null

  switch (raw.event) {
    case "token":
      return typeof payload.text === "string" ? { type: "token", text: payload.text } : null
    case "tool_start":
      return typeof payload.tool === "string"
        ? {
            type: "tool_start",
            tool: payload.tool,
            query: typeof payload.query === "string" ? payload.query : null,
          }
        : null
    case "sources":
      return Array.isArray(payload.sources) && payload.sources.every(isSourceLink)
        ? { type: "sources", sources: payload.sources }
        : null
    case "done":
      return { type: "done" }
    case "error":
      return typeof payload.message === "string"
        ? { type: "error", message: payload.message }
        : null
    default:
      return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function isSourceLink(value: unknown): value is SourceLink {
  return isRecord(value) && typeof value.title === "string" && typeof value.url === "string"
}
