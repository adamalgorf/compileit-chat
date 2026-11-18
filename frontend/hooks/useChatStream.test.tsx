import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { useChatStream } from "@/hooks/useChatStream"
import { MESSAGES } from "@/lib/api"

const USER = { username: "anna" }
const ACTIVE_KEY = "compileit-chat:active-conversation:anna"

const ANSWER = [
  'event: tool_start\ndata: {"tool": "search_website", "query": "kontakt"}\n\n',
  'event: token\ndata: {"text": "Mejla oss."}\n\n',
  'event: sources\ndata: {"sources": [{"title": "Kontakt", "url": "https://x/kontakt"}]}\n\n',
  "event: done\ndata: {}\n\n",
].join("")

const sse = (body: string) =>
  new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } })
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } })

const SAVED = {
  id: "saved-conversation",
  title: "Fråga",
  messages: [
    {
      role: "user",
      content: "Fråga",
      sources: [],
      status: null,
      created_at: "2026-11-18T10:00:00Z",
    },
    {
      role: "assistant",
      content: "Svar",
      sources: [],
      status: "done",
      created_at: "2026-11-18T10:00:01Z",
    },
  ],
}

describe("useChatStream", () => {
  const fetchMock = vi.fn<typeof fetch>()
  const callbacks = { onUnauthorized: vi.fn(), onSaved: vi.fn() }

  beforeEach(() => {
    localStorage.clear()
    vi.stubGlobal("fetch", fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    callbacks.onUnauthorized.mockReset()
    callbacks.onSaved.mockReset()
    vi.unstubAllGlobals()
  })

  const render = () => renderHook(() => useChatStream(USER, callbacks))

  it("streams an answer with the session cookie and reports the saved turn", async () => {
    fetchMock.mockResolvedValue(sse(ANSWER))
    const { result } = render()

    act(() => result.current.send("  Hur kontaktar man er?  "))

    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1]).toMatchObject({ content: "Mejla oss.", status: "done" })
    const [url, init] = fetchMock.mock.calls[0]!
    expect(String(url)).toMatch(/\/api\/chat$/)
    expect(init?.credentials).toBe("include")
    expect(JSON.parse(String(init?.body))).toEqual({
      conversation_id: result.current.conversationId,
      message: "Hur kontaktar man er?",
    })
    expect(localStorage.getItem(ACTIVE_KEY)).toBe(result.current.conversationId)
    expect(callbacks.onSaved).toHaveBeenCalled()
  })

  it("reopens the active conversation from the server after a reload", async () => {
    localStorage.setItem(ACTIVE_KEY, SAVED.id)
    fetchMock.mockResolvedValue(json(SAVED))

    const { result } = render()

    expect(result.current.loading).toBe(true)
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.conversationId).toBe(SAVED.id)
    expect(result.current.messages.map((m) => m.content)).toEqual(["Fråga", "Svar"])
    expect(String(fetchMock.mock.calls[0]![0])).toMatch(/\/api\/conversations\/saved-conversation$/)
  })

  it("opens another conversation and starts new ones with a fresh id", async () => {
    fetchMock.mockResolvedValue(json(SAVED))
    const { result } = render()
    const first = result.current.conversationId

    act(() => result.current.openConversation(SAVED.id))
    await waitFor(() => expect(result.current.messages).toHaveLength(2))
    act(() => result.current.newConversation())

    expect(result.current.messages).toEqual([])
    expect(result.current.conversationId).not.toBe(first)
    expect(result.current.conversationId).not.toBe(SAVED.id)
  })

  it("an expired session asks to log in again", async () => {
    fetchMock.mockResolvedValue(json({ detail: "Du behöver logga in." }, 401))
    const { result } = render()

    act(() => result.current.send("Hej"))

    await waitFor(() => expect(callbacks.onUnauthorized).toHaveBeenCalled())
    expect(result.current.messages[1]).toMatchObject({ status: "error" })
  })

  it("shows the backend's message when rate limited", async () => {
    fetchMock.mockResolvedValue(json({ detail: "För många frågor." }, 429))
    const { result } = render()

    act(() => result.current.send("Hej"))

    await waitFor(() =>
      expect(result.current.messages[1]).toMatchObject({
        status: "error",
        error: "För många frågor.",
      }),
    )
    expect(callbacks.onUnauthorized).not.toHaveBeenCalled()
  })

  it("treats a stream that ends without done/error as interrupted", async () => {
    fetchMock.mockResolvedValue(sse('event: token\ndata: {"text": "Halv"}\n\n'))
    const { result } = render()

    act(() => result.current.send("Hej"))

    await waitFor(() =>
      expect(result.current.messages[1]).toMatchObject({
        status: "error",
        error: MESSAGES.interrupted,
      }),
    )
  })

  it("stop aborts the request and marks the answer stopped", async () => {
    fetchMock.mockImplementation(
      (_url, init) =>
        new Promise((_resolve, reject) =>
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("aborted", "AbortError")),
          ),
        ),
    )
    const { result } = render()

    act(() => result.current.send("Hej"))
    act(() => result.current.stop())

    await waitFor(() => expect(result.current.messages[1]).toMatchObject({ status: "stopped" }))
  })
})
